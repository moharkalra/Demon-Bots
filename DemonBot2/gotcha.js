
      var helped = false;
      document.getElementById("fbc-imageselect-checkbox-1").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-2").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-3").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-4").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-5").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-6").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-7").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-8").onclick = function () { helped = false};
      document.getElementById("fbc-imageselect-checkbox-9").onclick = function () { helped = false};

      function declarePrompt(){
        const prompts = ["more fun", "more exciting", "more interesting", "more productive", "more creative", "spicier", "more meaningful", "more fun", "more important", "more active"]

        ind = Math.floor(Math.random() * 10);
        prompt = prompts[ind];
        document.getElementById("prompt").innerHTML = prompt;
      }
      function httpGetAsync(theUrl, callback)
      {
        var xmlHttp = new XMLHttpRequest();
        xmlHttp.onreadystatechange = function() {
          if (xmlHttp.readyState == 4 && xmlHttp.status == 200)
          callback(xmlHttp.responseText);
        }
        xmlHttp.open("GET", theUrl, true); // true for asynchronous
        xmlHttp.send(null);
      }
      function imageLoad(text){
        if (text==="ready"){
           document.getElementById("image").src = "http://localhost:8081/background.png";
           document.getElementById("behind").style.visibility = "hidden";
        }
        else{
          if (text==="reload1"){
             document.getElementById("image").src = "http://localhost:8081/backgroun1.png";
               setTimeout(() => {  httpGetAsync('http://localhost:8081/?status', imageLoad);}, 1000);
          }
          else if (text==="reload2"){
             document.getElementById("image").src = "http://localhost:8081/backgroun2.png";
               setTimeout(() => {  httpGetAsync('http://localhost:8081/?status', imageLoad);}, 1000);
          }
          else{

            setTimeout(() => {  httpGetAsync('http://localhost:8081/?status', imageLoad);}, 2000);
          }

        }
      }
      function help(){
        if(!helped){
          document.getElementById("fbc-imageselect-checkbox-1").checked = false;
          document.getElementById("fbc-imageselect-checkbox-2").checked = false;
          document.getElementById("fbc-imageselect-checkbox-3").checked = false;
          document.getElementById("fbc-imageselect-checkbox-4").checked = false;
          document.getElementById("fbc-imageselect-checkbox-5").checked = false;
          document.getElementById("fbc-imageselect-checkbox-6").checked = false;
          document.getElementById("fbc-imageselect-checkbox-7").checked = false;
          document.getElementById("fbc-imageselect-checkbox-8").checked = false;
          document.getElementById("fbc-imageselect-checkbox-9").checked = false;
          var rand = Math.floor(Math.random() * 8)+1;
          for(var i = 0; i<rand; i++){
              var box = Math.floor(Math.random() * 9)+1;
              var id = "fbc-imageselect-checkbox-"+box
              console.log(id)
              document.getElementById(id).checked = true;
          }
          helped = true;
        }
       }

       //HANDLE LISTENERS
       window.onload = httpGetAsync('http://localhost:8081/?status', imageLoad);
       window.onload = declarePrompt();
       document.getElementById("fbc-button-help").onclick = help;
       document.getElementById("fbc-button-verify").onclick = verify;

       function verify(){
         var verified = false;

         if(helped){
           verified = true;
         }else{

           if((document.getElementById("fbc-imageselect-checkbox-1").checked ||
            document.getElementById("fbc-imageselect-checkbox-2").checked ||
            document.getElementById("fbc-imageselect-checkbox-3").checked ||
            document.getElementById("fbc-imageselect-checkbox-4").checked ||
            document.getElementById("fbc-imageselect-checkbox-5").checked ||
            document.getElementById("fbc-imageselect-checkbox-6").checked ||
            document.getElementById("fbc-imageselect-checkbox-7").checked ||
            document.getElementById("fbc-imageselect-checkbox-8").checked ||
            document.getElementById("fbc-imageselect-checkbox-9").checked)  === false){
              verified = true;
            }
         }

         if(verified){
           window.location.href = "verified.html";
         }
         else{
           window.location.href = "unverified.html";
         }
       }
