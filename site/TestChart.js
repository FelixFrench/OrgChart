// On click, highlight this person and hide all others 
$(document).ready(function(){
	
	$(".person").click(function(e){
		e.stopPropagation();
		console.log("Person")
	});
	
	$(".subs, #viewport").click(function(e){
		e.stopPropagation();
		console.log("Background")
	});
	
	$(".chk").click(function(e){
	e.stopPropagation();
	console.log("chk")
	});
	
	$(".showHide").click(function(e){
		e.stopPropagation();
		console.log("showHide")
	});
	
	$(".showHide").change(function(e){
	e.stopPropagation();
	console.log("showHide")
	});
});