// On click, highlight this person and hide all others 
$(document).ready(function(){
	
	$(".manager, .worker").click(function(e){
		e.stopPropagation();
		console.log("Person")
		
		// Un-highlight everyone
		$(".manager, .worker").css("box-shadow", "0 0");
		$(".manager, .worker").css("padding", "0px");
		$(".subs").css("outline-color","rgba(0, 0, 0, 0.2)");
		
		// Uncheck all others
		$(".worksWith").not(this).prop( "checked", false );
		
		// Dim everyone
		$(".manager, .worker").css("opacity","0.3");
		
		// Un-dim this
		$(this).css("opacity","1");
		// Highlight this
		$(this).css("box-shadow", "2px 2px 10px rgba(0, 0, 0, 0.3)");
		$(this).css("padding", "1px");
		
		// Un-dim others that this works with
		if ($(this).data("works-with").length != 0){
			let worksWithString = '#' + $(this).data("works-with").join(", #");
			$(worksWithString).css("opacity","1");
		}
		

	});
	
	$(".subs, #viewport").click(function(e){
		e.stopPropagation();
		console.log("Background")
		// Un-highlight everyone
		$(".manager, .worker").css("box-shadow", "0 0");
		$(".manager, .worker").css("padding", "0px");
		$(".subs").css("outline-color","rgba(0, 0, 0, 1)");
		// Un-dim everyone
		$(".manager, .worker").css("opacity","1");
	});
	
	$(".chk").click(function(e){
		e.stopPropagation();
		console.log("chk")
	});
	
	$(".showHide").click(function(e){
		e.stopPropagation();
		console.log("showHideClick")
	});
	
	$(".chk").change(function(e){
		e.stopPropagation();
		console.log("showHideChange")
		var subs = $(this.parentNode.parentNode.parentNode).children(".subs");
		if (this.checked){
			$(subs).show()
		}else{
			$(subs).hide()
		}
	});
});