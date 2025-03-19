# OrgChart
 Create an interactive org chart webpage from Microsoft API calls.


To make your very own org chart:

 - Go to chat with your favourite colleage on the teams website https://teams.microsoft.com/v2/

 - Press F12 and go to the network tab

 - Now back on the webpage, click on the person's name, and go to their org chart.

 - That will have put a load of spam on the network tab, so filter for XHR.

 - Search for nam.loki.delve.office.com and click on one of the results.

 - Go to the request payload and scroll down to the 'authorization' element. It'll be a very long string starting "Bearer ".

 - Enter that entire string when prompted to by OrgChart.py.

 - If the python script fails, try a few more times :)

 - Enjoy your shiny new org chart!
