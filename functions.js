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
    log("setCookie: " + name + " = " + val);
    document.cookie = name + "=" + val;
}

function pollCookie() {
    cookie = getCookie("webauthn");
    if (cookie) {
	parts = cookie.split("|");
	//guid = parts[0];
	now = new Date();
	until = new Date(parts[1]);
	remain = (until.getTime() - now.getTime()) / 1000;
	log("pollCookie: " + cookie + " " + remain + "s remain until " + until);
	setLocaleDate("untiltime", until);
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

/**
 * Draw the progress bar
 */
function drawProgressBar(percent) {
	if (width == 0) {
		width = document.getElementById('Status').clientWidth;
	}
	var pixels = width * (percent / 100);  
	var html = '<div id="progress-wrapper" class="progress-wrapper" style="width: ' + width + 'px">';  
    html += '<div class="progress-bar" style="width: ' + pixels + 'px; background-color: #33cc33;"></div>';  
    html += '<div class="progress-text" style="width: ' + width + 'px">' + percent + '%</div>';  
    html += '</div>';  
	document.getElementById("ProgressBar").innerHTML = html;
}
	
/**
 * Get the custom tags as pairs (name, value) separated by HTML newline
 * Names are separated from their values also by HTML newline
 */
function getTags() {
	doc = document.getElementById('Required Tags');
	columns = doc.getElementsByTagName("td");
	length = columns.length;
	var ret=[];
	for (i=0; i<length;i+=2) {
		ret[i] = columns[i].firstChild.nodeValue;
		ret[i+1] = columns[i+1].firstChild.value;
	}
	return ret.join('<br/>');
}

/**
 * Set the values for custom tags 
 * they come as pairs (name, value) separated by HTML newline
 * Names are separated from their values also by HTML newline
 */
function setTags(tags) {
	var tokens = tags.split('<br/>');
	for (i=0; i<tokens.length;i+=2) {
		var id = tokens[i]+'_val';
		document.getElementById(id).firstChild.nodeValue = tokens[i+1];
	}
}

/**
 * Get the custom tags name separated by HTML newline
 */
function getTagsName() {
	doc = document.getElementById('Dataset Tags');
	columns = doc.getElementsByTagName("td");
	length = columns.length;
	var ret=[];
	var j=0;
	for (i=0; i<length;i+=2) {
		ret[j++] = columns[i].firstChild.nodeValue;
	}
	return ret.join('<br/>');
}

/**
 * Set the files to be uploaded or the first file to be downloaded
 */
function setFiles(files) {
    document.getElementById("Files").innerHTML = files;
}

/**
 * Add a file to be downloaded
 * Files are separated by HTML newline
 */
function addFile(file) {
    document.getElementById("Files").innerHTML += '<br/>'+file;
}

/**
 * Set the status during the upload/download
 */
function setStatus(status) {
    document.getElementById("Status").innerHTML = '<b>'+status+'</b>';
}

/**
 * Set the status during the upload/download
 */
function setDestinationDirectory(dir) {
    document.getElementById("DestinationDirectory").innerHTML = dir;
}

/**
 * Fill the form with the dataset info
 */
function getDatasetInfo() {
	var node = document.getElementById("TransmissionNumber");
	// Trim the value
	var value = node.value.replace(/^\s*/, "").replace(/\s*$/, "");
	if (value.length > 0) {
		var tags = getTagsName();
		document.TagFileDownloader.getDatasetInfo(value, tags);
	} else {
		alert('Transmission number can not be empty.');
	}
}

/**
 * Check if all required tags are present and have proper values
 */
function validateCustomTags() {
    var tagnames = customTags.split(',');
    for (i=0; i<tagnames.length; i++) {
    	var node = document.getElementById(tagnames[i]+'_id');
    	attr = node.attributes;
    	if (attr['required']) {
    		var value = node.value.replace(/^\s*/, "").replace(/\s*$/, "");
    		if (value.length == 0) {
    			alert('Tag "' + tagnames[i] + '" is required.');
    			return false;
    		}
    	}
    	if (attr['typestr'].value == 'date' && !document.TagFileUploader.validateDate(node.value)) {
    		alert('Bad value for tag "' + tagnames[i] + '".');
    		return false;
    	}
    }
    return true;
}

/**
 * Upload the files
 */
function uploadAll() {
	if (validateCustomTags()) {
    	document.TagFileUploader.uploadAll();
	}
}

/**
 * Download the files
 */
function downloadFiles() {
    document.TagFileDownloader.downloadFiles();
}

/**
 * Enables a button
 */
function setEnabled(id) {
    document.getElementById(id).disabled = false;
}

/**
 * Select directory for upload
 */
function uploadBrowse() {
    document.TagFileUploader.browse();
}

/**
 * Select directory for download
 */
function downloadBrowse() {
    document.TagFileDownloader.browse();
}

/**
 * Method "contains" for the Array object
 * returns true if an element is in the array, and false otherwise
 */
Array.prototype.contains = function ( elem ) {
   for (i in this) {
       if (this[i] == elem) return true;
   }
   return false;
}

/**
 * Set the required tags
 */
function setRequiredTags() {
    var tagnames = customTags.split(',');
    var tagtypes = typestr.split(',');
    var required = requiredTags.split(',');
    var html = '<table class="table-wrapper" id="Required Tags">\n';
    for (i=0; i<tagnames.length; i++) {
    	html += '<tr>\n'+
    			'<td class="tag-name">'+tagnames[i]+'</td>\n'+
    			'<td><input type="text" id="'+tagnames[i]+'_id" typestr="'+tagtypes[i]+'" ';
    	if (required.contains(tagnames[i])) {
    		html += 'required="required" ';
    	}
    	html += ' /></td>\n'+
    			'</tr>\n';
    }
    html += '</table>';
    document.getElementById('custom-tags').innerHTML = html;
}

/**
 * Set the dataset tags
 */
function setDatasetTags() {
    var tagnames = customTags.split(',');
    var html = '<table class="table-wrapper" rules="all" id="Dataset Tags">\n';
    for (i=0; i<tagnames.length; i++) {
    	html += '<tr>\n'+
    			'<td class="tag-name">'+tagnames[i]+'</td>\n'+
    			'<td id="'+tagnames[i]+'_val">';
    	for (j=0;j<40;j++) {
    		html += '&nbsp;';
    	}
    	html += ' </td>\n'+
    			'</tr>\n';
    }
    html += '</table>';
    document.getElementById('custom-tags').innerHTML = html;
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
var width = 0;

if(window.ActiveXObject) {
  ajax_request = new ActiveXObject("Microsoft.XMLHTTP");
}
else if(window.XMLHttpRequest) {
  ajax_request = new XMLHttpRequest();
}

if(ajax_request) {
  ajax_request.onreadystatechange = processSessionRequest;
}

/**
 * Add here the custom tags
 */
var customTags = 'Sponsor,Protocol,Investigator Last Name,Investigator First Name,Study Site Number,Patient Study ID,Study Visit,Image Type,Eye,Capture Date,Comment';
var typestr = 'text,text,text,text,text,text,text,text,text,date,text';
var requiredTags = 'Sponsor,Protocol,Investigator Last Name,Investigator First Name,Study Site Number,Patient Study ID,Study Visit,Image Type,Eye,Capture Date';
