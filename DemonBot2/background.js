

function getDomain(url){

  var path = url.split('//');
  if (path.length >1){
    path = path[1]
    domain = path.split('/')[0]
    if(domain==="mfihjmcgjggckplkkfgeeafpbpfihjbo"){
      domain = path
    }
    return domain
  }
  else{
    return "null"
  }
}

var lastUrl = "";
var enabled = true;

chrome.webRequest.onBeforeRequest.addListener(
    function(details) {
      console.log("entering redirect");
        var domain = lastUrl;
        var newUrl = "";
        console.log(lastUrl)
        console.log(getDomain(details.url))
        if (getDomain(details.url)=== "mfihjmcgjggckplkkfgeeafpbpfihjbo/gotcha.html"){
          ///post refresh image
          var message = "http://localhost:8081/" + "!refresh"
          var xmlHttp = new XMLHttpRequest();
          xmlHttp.open("POST", message, true); // true for asynchronous
          xmlHttp.send(null);
        }
        //make sure this is the verified page
        if (domain===getDomain(details.url) || domain === "mfihjmcgjggckplkkfgeeafpbpfihjbo/verified.html"){
         newUrl = details.url;
        }
        else{
          newUrl = chrome.runtime.getURL("gotcha.html");
          //POST the originally desired URL to the html page's verify button!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
          //post refresh image
          var message = "http://localhost:8081/" + "!refresh"
          var xmlHttp = new XMLHttpRequest();
          xmlHttp.open("POST", message, true); // true for asynchronous
          xmlHttp.send(null);
          message = "http://localhost:8081/" + "&" + details.url;
          xmlHttp = new XMLHttpRequest();
          xmlHttp.open("POST", message, true); // true for asynchronous
          xmlHttp.send(null);
        }

        return {redirectUrl: newUrl};
    },
    {
        urls: [
            "*://www.facebook.com/*",
            "*://www.instagram.com/*"
        ],
        types: ["main_frame", "sub_frame"]
    },
    ["blocking"]
);
chrome.tabs.onUpdated.addListener(onTabUpdated);
chrome.tabs.onActivated.addListener(onActiveUpdated);


function onTabUpdated(tabId, changeInfo, tab){

  onNewPage(tabId);
}
function onActiveUpdated(activeInfo){

    onNewPage(activeInfo.tabId);
}

function onNewPage(tabId){

  if(enabled){
    chrome.tabs.get(tabId, function(tab){
          let url = tab.url
          lastUrl = getDomain(url)
          console.log(lastUrl)
        })
  }
}
