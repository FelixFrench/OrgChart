##########################################################
# Creates the html of a webpage showing an entire OrgChart
# See README.txt for usage instructions
##########################################################

import asyncio, aiohttp
from aiohttp import ClientSession
from json import loads as loadJson
from time import time as timeNow
from re import match as reMatch
from datetime import datetime
import csv

treeFilename = 'site/OrgChart.html'
csvFilename = 'people.csv'
csvfile = open(csvFilename, 'w', newline='', encoding="utf-8")
csvwriter = csv.DictWriter(csvfile, ["givenName", "surname", "jobTitle", "companyName", "department", "office", "treeSize"], extrasaction='ignore')
csvwriter.writeheader()

# A type of exception to raise if the authentication has expired
class AuthExpired(Exception):
    pass

####################################################################################
# Sends a request to an API and waits for the response.
# Some error handling of common HTTP errors, returning None for a don't-care failure
####################################################################################
# Oopsie global variable. Stops all threads for a bit when the server is overloaded.
sleeping = False
async def AccessAPI(url: str, reqJson: dict, session: ClientSession) -> dict:
    while(True):
        try:
            # Send the request and wait for a response
            resp = await session.post(url, json = reqJson)

            # Raise an exception depending on the status
            resp.raise_for_status()

            # If no exception was raised then we can break, yippee!
            break

        except (
            aiohttp.ClientError,
            aiohttp.http_exceptions.HttpProcessingError,
        ) as e:
            errCode = getattr(e, "status", None)
            if errCode == 401: # Authentication expired - uh oh
                raise AuthExpired
            elif errCode == 404: # Not found - don't care
                print(url)
                print("\t[404]: Not found")
                return None
            elif errCode == 424: # Failed dependency - don't care
                print(url)
                print("\t[424]: Failed dependency")
                return None
            elif errCode == 429: # Too many requests - sleep all threads for a bit
                global sleeping
                
                if not sleeping:
                    # Set a global variable to tell all coroutines that we are sleeping
                    sleeping = True
                    # Release the processor for some time
                    await asyncio.sleep(0.1)
                    # Once this thread is done sleeping, unlock all coroutines.
                    sleeping = False
                else:
                    # If we're sleeping, check in regularly to see if we still are
                    while(sleeping):
                        await asyncio.sleep(0.001)
                continue
            elif errCode == 500: # Internal server error - don't care
                print(url)
                print("\t[500]: Internal server error")
                return None
            else: # Mystery error - spooky
                print("aiohttp exception for %s [%s]: %s" % (url, str(errCode), getattr(e, "message", None)))
                raise Exception("API access failed")
    
    return loadJson(await resp.text())

###################################################################################
# Makes a request to the Person endpoint to find some information about this person
###################################################################################
async def DoPerson(ID: str, reqJson: dict, session: ClientSession) -> dict:
    # Form the specific url for this person
    url = "https://nam.loki.delve.office.com/api/v1/person?&aadObjectId=%s&ConvertGetPost=true" % ID

    respJson = await AccessAPI(url, reqJson, session=session)

    person = dict()
    
    # Lots of awful catching to make sure we don't try to use a directionary index that doesn't exist
    if respJson is not None:
        names = respJson.get("names")
        if names is not None:
            if len(names) > 0:
                # If a person has multiple names, the first is used.
                if "value" in names[0]:
                    person["givenName"] = names[0]["value"].get("givenName")
                    person["surname"]   = names[0]["value"].get("surname")
        
        workDetails = respJson.get("workDetails")
        if workDetails is not None:
            if len(workDetails) > 0:
                # If a person has multiple work details, the first is used.
                if "value" in workDetails[0]:
                    person["companyName"] = workDetails[0]["value"].get("companyName")
                    person["jobTitle"]    = workDetails[0]["value"].get("jobTitle")
                    person["department"]  = workDetails[0]["value"].get("department")
                    person["office"]      = workDetails[0]["value"].get("office")

    return person

###############################################################################################
# Makes a request to the WorkingWith endpoint to find the list of people this person works with
###############################################################################################
async def DoWorkingWith(ID: str, reqJson: dict, session: ClientSession) -> set:  
    # Form the specific url for this person
    url = "https://nam.loki.delve.office.com/api/v1/workingwith?&aadObjectId=%s&ConvertGetPost=true" % ID

    respJson = await AccessAPI(url, reqJson, session=session)
    
    # If nothing is returned, presume this person has no worksWiths
    if respJson is None:
        worksWith = set()
    else:
        worksWith = set([colleague["aadObjectId"] for colleague in respJson["value"]])
        
    return worksWith

##############################################################################################
# Makes a request to the Organization endpoint to find the list of people reporting to someone
##############################################################################################
async def DoOrganization(ID: str, reqJson: dict, session: ClientSession) -> set:
    # Form the specific url to get this person's org
    url = "https://nam.loki.delve.office.com/api/v1/organization?&aadObjectId=%s&ConvertGetPost=true" % ID

    respJson = await AccessAPI(url, reqJson, session=session)
    
    # If nothing is returned, presume this person has no directs
    if respJson is None:
        subs = set()
    else:
        # Add each direct (sub-ordinate) of this person to edges, with the manager id of this person
        subs = set([direct['aadObjectId'] for direct in respJson["directs"]])

    return subs

#################################################################################################
# The recursive function for the data gathering.
# First waits for an API call to find out the subs of this node,
# Then sets up a gather to get this person's info, and worksWith, and do GetOrg for all its subs
# There has to be two awaits in this function because the next GetOrg functions cannot fire until
#  DoOrganisation has been done
#################################################################################################
async def GetOrg(ID: str, reqJson: dict, session: ClientSession) -> list:
    # Get this person's subs
    subsIDs = await DoOrganization(ID, reqJson, session)

    # Create tasks to get this node's person info & working with, and the orgs of all child nodes.
    personCoro = DoPerson(ID, reqJson, session)
    wwCoro = DoWorkingWith(ID, reqJson, session)
    tasks = [personCoro, wwCoro] + [GetOrg(subID, reqJson, session) for subID in subsIDs]

    # Run all the tasks async-ly
    personDict, ww, *subs = await asyncio.gather(*tasks)

    # Form this person's branch of the org tree which will be returned
    tree = {"ID": ID} | personDict
    tree["worksWith"] = ww

    # Sort the subs in order of the number of people in their tree (including themselves)
    tree["Subs"] = sorted(subs, key=lambda e: e["treeSize"], reverse=True)
    tree["treeSize"] = sum([sub["treeSize"] for sub in subs]) + 1

    return tree

######################################################
# This async function starts off the GetOrg recursion.
######################################################
async def AsyncWrapper(rootSMTP: str, reqJson: dict, **kwargs) -> dict:    
    async with ClientSession() as session:
        # Get the root's aadObjectID from the provided email address using a person request
        url = "https://nam.loki.delve.office.com/api/v2/person?&smtp=%s&ConvertGetPost=true" % rootSMTP
        respJson = await AccessAPI(url, reqJson, session=session)

        # If anything looks dodgy, just say the email address is unrecognised
        if respJson is None:
            Exception("Unrecognised email address")
        rootID = respJson["person"].get("aadObjectId")
        if rootID is None:
            Exception("Unrecognised email address")

        # Begin recursion
        return await GetOrg(rootID, reqJson, session)

#######################################################
# This function hides everything async from the caller.
#######################################################
def OrgChart(rootSMTP: str, auth: str) -> dict:
    reqJson = { "X-ClientType" : "Teams",
    "authorization" : auth }
    return asyncio.run(AsyncWrapper(rootSMTP, reqJson))



###########################################################################
# Add a person to the tree. This may be the manager of a team, or a worker.
# Have to be careful as any attribute can be None 
###########################################################################
# Awful cursed global variable god forgive me
showHideID = 0
# Person should have {ID, givenName, surname, companyName, jobTitle, department, office}
def AddPerson(htmlFile, L, isManager, person):
    # Opening div tag
    htmlFile.write("<div id=\"%s\" class=\"" % str(person["ID"]))
    htmlFile.write("manager" if isManager else "worker")
    htmlFile.write(" L%s\"" % str(L))
    htmlFile.write("data-works-with=\"%s\">" % str(person["worksWith"]).replace("'", "&#34;"))
    
    # Text part
    htmlFile.write("<div class=\"personText\"> <p><b>")
    if "givenName"   in person : htmlFile.write("%s "    % str(person["givenName"]  ))
    if "surname"     in person : htmlFile.write("%s<br>" % str(person["surname"]    ))
    htmlFile.write("</b>")
    if "jobTitle"    in person : htmlFile.write("%s<br>" % str(person["jobTitle"]   ))
    if "department"  in person : htmlFile.write("%s<br>" % str(person["department"] ))
    if "companyName" in person : htmlFile.write("%s<br>" % str(person["companyName"]))
    if "office"      in person : htmlFile.write("%s<br>" % str(person["office"]     ))
    htmlFile.write("</p></div>")#.personText

    # Add this person to the csv log
    csvwriter.writerow(person)
    
    # Buttons part
    if isManager:
        htmlFile.write("<div class=\"personButtons\">")
        # Every button has a label, and each pair has to share a unique ID
        global showHideID
        htmlFile.write("<input type=\"checkbox\" class=\"chk\"  id=chk%s checked=\"true\">" % str(showHideID))
        htmlFile.write("<label class=\"showHide\" for=chk%s></label></div>" % str(showHideID))
        showHideID += 1
        
    htmlFile.write("</div>")#.worker
    
###################################################################
# Recursively add all teams to the tree. 
# A team has the form team{person, subs{team[], workers{person[]}}}
###################################################################
def AddTeam(htmlFile, team, depth):
    htmlFile.write("<div class=\"team\">")
    
    # Draw the manager
    AddPerson(htmlFile, depth, True, team)
    
    htmlFile.write("<div class=\"subs\">")
    # Draw any/all sub-teams
    for sub in team["Subs"]:
        if len(sub["Subs"]) > 0:
            AddTeam(htmlFile, sub, depth + 1)

    htmlFile.write("<div class=\"workers\">")
    # Draw any/all workers
    for sub in team["Subs"]:
        if len(sub["Subs"]) == 0:
            # Id, class and worksWith
            AddPerson(htmlFile, depth + 1, False, sub)
    htmlFile.write("</div></div></div>")#.workers, .subs, .team

###############################################################################################
# Takes the dictionay created during the API access phase and formats it into some lovely html.
# Starts a recursive process of AddTeam
###############################################################################################
def DisplayTree(tree, filename):
    htmlFile = open(filename, 'w', encoding="utf-8")

    # Write the HTMl head and start the body
    htmlFile.write("<!DOCTYPE html><html><head><title>OrgChart</title>")
    htmlFile.write("<link rel=\"icon\" type=\"image/x-icon\" href=\"favicon.ico\">")
    htmlFile.write("<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">")
    htmlFile.write("<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>")
    htmlFile.write("<link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk&display=swap\" rel=\"stylesheet\">")
    htmlFile.write("<link rel=\"stylesheet\" href=\"OrgChart.css\">")
    htmlFile.write("<script src=\"https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js\"></script>")
    htmlFile.write("<script src=\"http://jquery-csv.googlecode.com/git/src/jquery.csv.js\"></script>")
    htmlFile.write("<script src=\"OrgChart.js\"></script>")
    htmlFile.write("</head><h1>")
    htmlFile.write("OrgChart ")
    htmlFile.write(datetime.now().strftime("%d/%m/%y"))
    htmlFile.write("</h1><body><div id=\"viewport\">")

    # Add the tree
    AddTeam(htmlFile, tree, 0)

    # Closeup the HTML
    htmlFile.write("</div></body><html>")



##########################################################
# 1. Get the email of the root
# 2. Get the saved auth code from a file (if available)
# 3. Run the OrgChart process to get the data from the API
# 4. Run DisplayTree to turn that data into nice HTML
##########################################################
if __name__ == "__main__":

    # Get the root initials off the user
    rootSMTP = input("\nEnter the email address of the top person in the org chart\n")
    if not reMatch(r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])""", rootSMTP):
        raise Exception("Invalid email address")

    print("--- Timer start ---")
    start_time = timeNow()

    # A file is used to store the authentication credentials. These expire after 30 mins (maybe?) but saves a bit of time normally.
    authFileName = "_Auth.txt" # Includes extension


    # Try to load the auth header from a file, catching the case that the file doesn't exist.
    try:
        with open(authFileName, 'r') as authFile:
            auth = authFile.read().replace('\n', '')
    
    except(FileNotFoundError):
        auth = input("Enter authorization\n")
        with open(authFileName, 'w') as authFile:
            authFile.write(auth)
        start_time = timeNow()


    # Try to find the tree for this root, catching the case that the server responds saying the auth is expired.
    try:
        tree = OrgChart(rootSMTP, auth)

    except(AuthExpired):
        auth = input("Re-enter authorization\n")
        with open(authFileName, 'w') as authFile:
            authFile.write(auth)
        start_time = timeNow()
        tree = OrgChart(rootSMTP, auth)


    print("Organization done")
    print("--- %s seconds ---" % (timeNow() - start_time))
    print("Organisation saved as", csvFilename)

    DisplayTree(tree, treeFilename)

    print("DisplayTree done")
    print("--- %s seconds ---" % (timeNow() - start_time))
    print("Tree saved as", treeFilename)
