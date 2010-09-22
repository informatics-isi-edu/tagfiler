function setDatasetLink(div_id, datasetLink) {
  html_link = "<a target='_blank' href='" + datasetLink +
        "'>" + datasetLink + "</a>";
  document.getElementById(div_id).innerHTML = html_link;
}

function log(msg) {
    var node = document.getElementById("javascriptlog");
    if (node) {
	node.innerHTML = (new Date()).toLocaleTimeString() + " " + msg + "<br />" + node.innerHTML
    }
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
    //    startSessionTimer(pollmins * 60 * 1000);
    //startCookieTimer(pollmins * 60 * 1000 / 6);
    startCookieTimer(1000);
}

function clearSessionTimer() {
    if (timerset) {
	clearTimeout(timer);
	timerset = 0;
    }
}

/**
 * Starts the session check timer with a given delay time (millis)
 */
function startSessionTimer(t) {
    clearSessionTimer();
    timer = setTimeout("runSessionRequest()", t);
    timerset = 1;
}

function startCookieTimer(t) {
    clearSessionTimer();
    timer = setTimeout("pollCookie()", t);
    timerset = 1;
}

/**
 * Runs the Ajax request to retrieve the expiration
 */
function runSessionRequest() {
  if(ajax_request) {
      if (ajax_request.readystate != 0) {
	  ajax_request.abort();
      }
      log("runSessionRequest: starting GET " + expiration_check_url);
      ajax_request.open("GET", expiration_check_url);
      ajax_request.setRequestHeader("User-agent", "Tagfiler/1.0");
      ajax_request.onreadystatechange = processSessionRequest;
      ajax_request.send(null);
  }
}

function getCookie(name) {
    cookies = document.cookie.split(";");
    for (c=0; c<cookies.length; c++) {
	kv = cookies[c].split("=");
	if (kv[0] == name) {
	    return unescape(kv[1]);
	}
    }
    return null;
}

function setCookie(name, val) {
    document.cookie = name + "=" val;
}

function pollCookie() {
    cookie = getCookie("webauthn");
    if (cookie) {
	parts = cookie.split("|");
	//guid = parts[0];
	now = new Date();
	until = new Date(parts[1]);
	remain = (until.getTime() - now.getTime()) / 1000;
	setLocaleDate("untiltime", until);
	log("pollCookie: " + remain + "s remain");
	if (remain < expiration_warn_mins * 60) {
	    log("pollCookie: cookie suggests session is near warning period");
	    runSessionRequest();
	}
	else {
	    //startCookieTimer(expiration_poll_mins * 60 * 1000 / 6);
	    startCookieTimer(1000);
	}
    }
    else {
	log("pollCookie: no cookie found");
	runSessionRequest();
    }
}

function runLogoutRequest() {
    if (ajax_request) {
	if (ajax_request.readystate != 0) {
	    ajax_request.abort();
	}
	ajax_request.open("POST", "/webauthn/logout");
	ajax_request.setRequestHeader("User-agent", "Tagfiler/1.0");
	ajax_request.setRequestHeader("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8"); 
	ajax_request.onreadystatechange = processLogoutRequest;
	ajax_request.send("action=logout");
    }
}

function runExtendRequest() {
    if (ajax_request) {
	if (ajax_request.readystate != 0) {
	    ajax_request.abort();
	}
	ajax_request.open("GET", "/webauthn/session?action=extend");
	ajax_request.setRequestHeader("User-agent", "Tagfiler/1.0");
	ajax_request.onreadystatechange = processSessionRequest;
	ajax_request.send(null);
    }
}

function processLogoutRequest() {
    if (ajax_request.readyState == 4) {
	clearSessionTimer();
	window.location = "/tagfiler/"
    }
}

function redirectNow() {
    var node = document.getElementById("javascriptlog");
    clearSessionTimer();
    if (warn_window) {
	log("redirectNow: closing warning window");
	warn_window.close();
    }
    if (node) {
	alert("About to redirect to login page");
    }
    window.location='/webauthn/login?referer=' + encodeURIComponent(window.location);
}

/**
 * Processes the response from the Ajax request
 */
function processSessionRequest() {
  if(ajax_request && ajax_request.readyState == 4) {
      log("processSessionRequest: readyState=4 status=" + ajax_request.status);
      log("window.location=" + window.location);
    if(ajax_request.status == 200) {
      response_pairs = ajax_request.responseText.split("&");
      until = null;
      secsremain = 0;
      for(i=0; i < response_pairs.length; i++) {
	  pair_fields = response_pairs[i].split("=");
	  if(pair_fields[0] == 'until') {
	      until = new Date(unescape(pair_fields[1]));
	      log("processSessionRequest: until=" + unescape(pair_fields[1]));
	      setLocaleDate("untiltime", until);
	  }
	  if(pair_fields[0] == 'secsremain') {
	      secsremain = parseInt(unescape(pair_fields[1]));
	      log("processSessionRequest: secsremain=" + secsremain);
	  }
      }

      cookie = getCookie("webauthn");
      parts = cookie.split("|");
      setCookie("webauthn", encodeURIComponent(parts[0] + "|" + until.toGMTString() + "|" + secsremain));

      if (secsremain < 1) {
	  secsremain = 1;
	  log("processSessionRequest: clamping secsremain to 1");
      }	
	      
      if ( secsremain < expiration_warn_mins * 60) {
	  if (!warn_window || warn_window.closed) {
	      log("processSessionRequest: raising warning window");
	      warn_window = (window.open(expiration_warn_url,
					 warn_window_name,
					 warn_window_features));
	  }
	  startSessionTimer(secsremain * 1000);
      }
      else {
	  //startSessionTimer(expiration_poll_mins * 60 * 1000);
	  startCookieTimer(1000);
      }
      return;
    }
    else {
	// usually 404 ends a session
	redirectNow();
    }
  }
}

var timer = 0;
var timerset = 0;
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

