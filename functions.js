function setDatasetLink(div_id, datasetLink) {
  html_link = "<a target='_blank' href='" + datasetLink +
        "'>" + datasetLink + "</a>";
  document.getElementById(div_id).innerHTML = html_link;
}

function localizeDate(id) {
    var node = document.getElementById(id);
    if (node) {
	var d = new Date(node.innerHTML);
	node.innerHTML = d.toLocaleTimeString();
    }
}

function setLocaleDate(id, d) {
    var node = document.getElementById(id);
    if (node) {
	node.innerHTML = d.toLocaleTimeString();
    }
}

/**
 * Runs the session poll - argument is in minutes
 *
 */
function runSessionPolling(m) {
    expiration_poll_mins = m;
    startSessionTimer(m * 60 * 1000);
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
      response_pairs = ajax_request.responseText.split("&");
      next_poll = 0;
      until = null;
      for(i=0; i < response_pairs.length; i++) {
	  pair_fields = response_pairs[i].split("=");
	  if(pair_fields[0] == 'until') {
	      until = new Date(unescape(pair_fields[1]));
	      setLocaleDate("untiltime", until);
	      break;
	  }
      }

      // poll at regular interval until session is over
      now = new Date();
      msecleft = until.valueOf() - now.valueOf();
      minsleft = msecleft / 60 / 1000;
      if (msecleft < expiration_poll_mins * 60 * 1000) {
	  startSessionTimer(msecleft);
      }
      else {
	  startSessionTimer(expiration_poll_mins * 60 * 1000);
      }
    }
    else if(ajax_request.status == 404) {
      // redirect to the login page
      window.location='/webauthn/login';
    }
    else {
	window.location='/webauthn/status';
    }
  }
}

var expiration_poll_mins = 1;
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

