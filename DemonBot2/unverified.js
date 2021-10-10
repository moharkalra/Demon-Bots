
      var helped = false;
    

      function redirecting(){
        setTimeout(function() {
          document.getElementById("redirect").style.visibility='visible';
          setTimeout(function() {
            newPage("gotcha.html");
          }, 1000);
        }, 1000);
      }
      function newPage(url){
          window.location.replace(url);
      }
      window.onload = redirecting;
