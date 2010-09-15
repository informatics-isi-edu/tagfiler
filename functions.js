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
function runSessionPolling(pollmins, warnmins) {
    expiration_poll_mins = pollmins;
    expiration_warn_mins = warnmins;
    startSessionTimer(pollmins * 60 * 1000);
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
      if (ajax_request.readystate != 0) {
	  ajax_request.abort();
      }
      ajax_request.open("GET", expiration_check_url);
      ajax_request.setRequestHeader("User-agent", "Tagfiler/1.0");
      ajax_request.onreadystatechange = processSessionRequest;
      ajax_request.send(null);
  }
}

function runLogoutRequest() {
    if (ajax_request) {
	if (ajax_request.readystate != 0) {
	  ajax_request.abort();
	}
      ajax_request.open("POST", "/webauthn/logout");
      ajax_request.setRequestHeader("User-agent", "Tagfiler/1.0");
      ajax_request.onreadystatechange = processLogoutRequest;
      ajax_request.send(null);
    }
}

function processLogoutRequest() {
    if (ajax_request.readyState == 4) {
	window.location = "/tagfiler/"
    }
}

/**
 * Processes the response from the Ajax request
 */
function processSessionRequest() {
  if(ajax_request && ajax_request.readyState == 4) {
    if(ajax_request.status == 200) {
      response_pairs = ajax_request.responseText.split("&");
      until = null;
      for(i=0; i < response_pairs.length; i++) {
	  pair_fields = response_pairs[i].split("=");
	  if(pair_fields[0] == 'until') {
	      until = new Date(unescape(pair_fields[1]));
	      setLocaleDate("untiltime", until);

	      // poll at regular interval until session is over
	      now = new Date();
	      msecleft = until.valueOf() - now.valueOf();
	      minsleft = msecleft / 60 / 1000;
	      if (msecleft < expiration_poll_mins * 60 * 1000) {
		  startSessionTimer(msecleft + 250);
	      }
	      else {
		  if (msecleft > 0 && msecleft < expiration_warn_mins * 60 * 1000) {
		      warn_window = (window.open(expiration_warn_url,
						 warn_window_name,
						 warn_window_features));
		  }
		  startSessionTimer(expiration_poll_mins * 60 * 1000);
	      }
	      return;
	  }
      }
      // not finding until field is a failure?
      if (warn_window) {
	  warn_window.close();
      }
      window.location='/webauthn/login';
    }
    else if(ajax_request.status == 404) {
	// redirect to the login page
	if (warn_window) {
	    warn_window.close();
	}
	window.location='/webauthn/login';
    }
    else {
	window.location='/webauthn/login';
    }
  }
}

var expiration_poll_mins = 1;
var expiration_warn_mins = 2;
var expiration_check_url = "/webauthn/session";
var expiration_warn_url = "/webauthn/session?action=prompt";
var warn_window_name = "SessionIdleWarning";
var warn_window_features = "height=400,width=600,resizable=yes,scrollbars=yes,status=yes,location=no";
var ajax_request = null;
var warn_window = null;
var until = null;

if(window.ActiveXObject) {
  ajax_request = new ActiveXObject("Microsoft.XMLHTTP");
}
else if(window.XMLHttpRequest) {
  ajax_request = new XMLHttpRequest();
}

if(ajax_request) {
  ajax_request.onreadystatechange = processSessionRequest;
}

