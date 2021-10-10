var helped = false;


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
function redirecting(){
  setTimeout(function() {
    document.getElementById("redirect").style.visibility='visible';
    setTimeout(function() {
      httpGetAsync("http://localhost:8081/@url", newPage);
    }, 1000);
  }, 1000);
}
function newPage(url){
    window.location.replace(url);
}
window.onload = redirecting;
