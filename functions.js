function setDatasetLink(div_id, datasetLink) {
  html_link = "<a target='_blank' href='" + datasetLink +
        "'>" + datasetLink + "</a>";
  document.getElementById(div_id).innerHTML = html_link;
}

/**
 * Starts the session check timer with a given delay time (millis)
 */
function startSessionTimer(t) {
  setTimeout("runSessionRequest()", t);
}

/**
 * Runs the Ajax request to retrieve the expiration
 */
function runSessionRequest() {
  if(ajax_request) {
    ajax_request.open("GET", expiration_check_url);
    ajax_request.send(null);
  }
}

/**
 * Processes the response from the Ajax request
 */
function processSessionRequest() {
  if(ajax_request.readyState == 4) {
    if(ajax_request.status == 200) {
      expire_date_str = unescape(ajax_request.responseText.replace("until=", ""));
      // update time variable with new expiration time and restart
      // startSessionTimer();
    }
    else if(ajax_request.status == 404) {
      // redirect to the login page
      window.location='/webauthn/login';
    }
  }
}

var expiration_check_url = "/webauthn/session";
var ajax_request = null;
if(window.ActiveXObject) {
  ajax_request = new ActiveXObject("Microsoft.XMLHTTP");
}
else if(window.XMLHttpRequest) {
  ajax_request = new XMLHttpRequest();
}

if(ajax_request) {
  ajax_request.onreadystatechange = processSessionRequest;
}

