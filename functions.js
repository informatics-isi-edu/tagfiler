/* 
 * Copyright 2010 University of Southern California
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *    http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var expiration_warning = true;
var extend_time = 0;

function setExtendTime() {
	extend_time = (new Date()).getTime();
}

function enableExpirationWarning() {
	expiration_warning = true;
}

function disableExpirationWarning() {
	expiration_warning = false;
}

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

/**
 * Starts the extend request with a given delay time (millis)
 */
function startExtendSessionTimer(t) {
    clearSessionTimer();
    timer = setTimeout("runExtendRequest()", t);
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
    cookie = null;
    for (c=0; c<cookies.length; c++) {
	kv = cookies[c].split("=");
	if (kv[0] == name) {
	    //log ('getCookie: found ' + kv[1]);
	    cookie = decodeURIComponent(kv[1]);
	}
    }
    return cookie;
}

function setCookie(name, val) {
    val = encodeURIComponent(decodeURIComponent(val));
    //log("setCookie: " + name + " = " + val);
    document.cookie = name + "=" + val + "; path=/";
}

function pollCookie() {
    cookie = getCookie("webauthn");
    if (cookie) {
	parts = cookie.split("|");
	//guid = parts[0];
	now = new Date();
	until = new Date(parts[1]);
	remain = (until.getTime() - now.getTime()) / 1000;
	//log("pollCookie: " + remain + "s remain until " + until);
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
	alert("About to redirect at end of session");
    }
    if (redirectToLogin) {
	window.location='/webauthn/login?referer=' + encodeURIComponent(window.location);
    }
    else {
	window.location = window.location;
    }
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
	      until = new Date(decodeURIComponent(pair_fields[1]));
	      log("processSessionRequest: until=" + decodeURIComponent(pair_fields[1]));
	      setLocaleDate("untiltime", until);
	  }
	  if(pair_fields[0] == 'secsremain') {
	      secsremain = parseInt(decodeURIComponent(pair_fields[1]));
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
	  if (!expiration_warning) {
	  	startExtendSessionTimer(1000);
	  	return;
	  }
	  if (((new Date()).getTime() - extend_time) > (expiration_warn_mins * 60 * 1000) && (!warn_window || warn_window.closed)) {
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

function getTagsArray() {
    var ret=[];
    var pos=0;
    
    tagblock = document.getElementById('Required Tags');
    if (!tagblock) return ret;

    inputtags = tagblock.getElementsByTagName("input");
    log ('got '  + inputtags.length + ' input elements');
    for (i=0; i<inputtags.length; i++) {
	var tagname = inputtags[i].getAttribute("name");
	var tagval = inputtags[i].value;
	log ('got input tag ' + tagname + ' = ' + tagval);
	ret[pos] = tagname;
	ret[pos+1] = tagval;
	pos += 2;
    }

    selecttags = tagblock.getElementsByTagName("select");
    log ('got '  + selecttags.length + ' select elements');
    for (i=0; i<selecttags.length; i++) {
	var tagname = selecttags[i].getAttribute("name");
	var tagval = selecttags[i].value;
	log ('got select tag ' + tagname + ' = ' + tagval);
	ret[pos] = tagname;
	ret[pos+1] = tagval;
	pos += 2;
    }

    return ret;
}

/**
 * Get the custom tags as pairs (name, value) separated by HTML newline
 * Names are separated from their values also by HTML newline
 */
function getTags() {
    var ret = getTagsArray().join('<br/>');
    log("getTags() = " + ret );
    return ret;
}


/**
 * Set the values for custom tags 
 * they come as pairs (name, value) separated by HTML newline
 * Names are separated from their values also by HTML newline
 */
function setTags(tags) {
    log("setTags(" + tags + ")");
    var tokens = tags.split('<br/>');
    for (i=0; i<tokens.length;i+=2) {
	if (tokens[i] == null || tokens[i+1] == null) continue;
	var id = tokens[i]+'_val';
	if (tokens[i+1].length > 0) {
	    document.getElementById(id).value = tokens[i+1];
	}
    }
}

/**
 * Set the Dataset Name
 */
function setTransmissionNumber(value) {
	document.getElementById("TransmissionNumber").value = value;
}

/**
 * Get the custom tags name separated by HTML newline
 */
function getTagsName() {
    var ret = getRequiredTagsName().join('<br/>');
    log ("getTagsName() = " + ret);
    return ret;
}

/**
 * Get the applet config
 */
function getConfig() {
	var ret = '';
	var options = window.location.search.substring(1).split('&');
	for (var i=0; i<options.length; i++) {
		if (options[i].indexOf('type=') == 0) {
			ret = options[i];
			break;
		}
	}
	return ret;
}

/**
 * Get the custom tags name
 */
function getRequiredTagsName() {
    var ret = [];
    var pos=0;
    var tagsArray = getTagsArray();
    for (i=0; i<tagsArray.length; i+=2) {
	ret[pos++] = tagsArray[i];
    }
    log("getRequiredTagsName() = " + ret);
    return ret;
}

/**
 * Set the files to be uploaded or the first file to be downloaded
 */
function setFiles(files) {
	var node = document.getElementById('Required Tags');
	if (!hasSize && node.attributes['template'] != null && node.attributes['template'].value == 'DIRC') {
		var tree = document.getElementById('files-tree');
		tree.style.width = node.style.width = node.clientWidth+'px';
		tree.style.height = node.style.height = node.clientHeight+'px';
		hasSize = true;
	}
	var names = files.split('<br/>');
	names.sort(compareIgnoreCase);
    document.getElementById("Files").innerHTML = names.join('<br/>');
}

/**
 * Compares two strings lexicographically, ignoring case differences.
 */
function compareIgnoreCase(str1, str2) {
	var val1 = str1.toLowerCase();
	var val2 = str2.toLowerCase();
	if (val1 == val2) {
		return 0;
	} else if (val1 < val2) {
		return -1;
	} else {
		return 1;
	}
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
    document.getElementById("Browse").value = dir;
}

/**
 * Fill the form with the dataset info
 */
function getDatasetInfo() {
	var node = document.getElementById("TransmissionNumber");
	// Trim the value
	var value = node.value.replace(/^\s*/, "").replace(/\s*$/, "");
	if (value.length > 0) {
		var version = document.getElementById("Version").value.replace(/^\s*/, "").replace(/\s*$/, "");
		if (version.length > 0) {
			if (isNaN(parseInt(version)) || version.length != ("" + parseInt(version)).length) {
				alert('Invalid value for the version.');
				return;
			}
		}
		var tags = getTagsName();
		document.TagFileDownloader.getDatasetInfo(value, version, tags);
	} else {
		alert('Dataset Name can not be empty.');
	}
}

/**
 * Check if all required tags are present and have proper values
 * Check if the dataset name needs to be provided
 */
function validateUpload() {
    var tagnames = getRequiredTagsName();
    for (i=0; i<tagnames.length; i++) {
		log("validating tag " + tagnames[i]);
    	var node = document.getElementById(tagnames[i]+'_id');
    	var value = node.value.replace(/^\s*/, "").replace(/\s*$/, "");
    	var attr = node.attributes;
    	if (value.length > 0) {
	    	if (attr['typestr'].value == 'date' && !document.TagFileUploader.validateDate(value) || 
	    		attr['typestr'].value == 'int8' && (isNaN(parseInt(value)) || value.length != ("" + parseInt(value)).length) ||
	    		attr['typestr'].value == 'float8' && isNaN(parseFloat(value)))
	    	{
	    		alert('Bad value for tag "' + tagnames[i] + '".');
	    		return false;
	    	}
    	} else if (attr['required']) {
			alert('Tag "' + tagnames[i] + '" is required.');
			return false;
    	}
    }
    if (document.getElementById('DatasetName Set').checked && 
    	document.getElementById('TransmissionNumber').value.replace(/^\s*/, "").replace(/\s*$/, "").length == 0) {
			alert('You need to provide a dataset name.');
			return false;
    }
    return true;
}

/**
 * Upload the files
 */
function uploadAll(files) {
	if (validateUpload()) {
    	document.TagFileUploader.uploadAll(files);
	}
}

/**
 * Download the files
 */
function downloadFiles(files) {
    document.TagFileDownloader.downloadFiles(files);
}

/**
 * Enables a button
 */
function setEnabled(id) {
    document.getElementById(id).disabled = false;
}

/**
 * Makes visible a button
 */
function setVisibility(id, value) {
    document.getElementById(id).style.visibility = value;
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
 * Get the checksum switch
 */
function getChecksum() {
	return "" + document.getElementById('cksum').checked;
}

/**
 * Get the dataset name
 */
function getDatasetName() {
	return document.getElementById('TransmissionNumber').value;
}

/**
 * Enable the Upload resume Button
 */
function enableUploadResume() {
	if (document.getElementById('DatasetName Set').checked) {
		document.getElementById('Resume').style.visibility = "visible";
	}
}

/**
 * Enable setting a dataset name
 */
function setDatasetName() {
	document.getElementById('TransmissionNumber').disabled = false;
	if (document.getElementById("Browse").value.replace(/^\s*/, "").replace(/\s*$/, "").length > 0) {
		document.getElementById('Resume').style.visibility = "visible";
	}
}

/**
 * Disable setting a dataset name
 */
function resetDatasetName() {
	var elem = document.getElementById('TransmissionNumber');
	elem.disabled = true;
	elem.value = "";
	document.getElementById('Resume').style.visibility = "hidden";
}

/**
 * Delete a dataset and all its contains
 * dataname = the dataset name (predicate)
 * url = the URL to POST the request
 */
function deleteAll(dataname, url) {
	var answer = confirm ('Do you want to delete the dataset "' + dataname + '" with all its content?');
	if (!answer) {
		return;
	}
	document.body.style.cursor = "wait";
	ajax_client.open("DELETE", url+'/', true);
	ajax_client.setRequestHeader("User-agent", "Tagfiler/1.0");
	ajax_client.onreadystatechange = function() {
		if(ajax_client.readyState == 4) {
			ajax_client.open("DELETE", url, true);
			ajax_client.setRequestHeader("User-agent", "Tagfiler/1.0");
			ajax_client.onreadystatechange = processDelete;
			ajax_client.send(null);
			return;
		}
	}
	ajax_client.send(null);
}

/**
 * Delete a dataset or its contains
 * dataname = the dataset name (predicate)
 * url = the URL to POST the request
 */
function deleteDataset(dataname, url) {
	var param = '';
	if (url.lastIndexOf('/') == url.length-1) {
		param = 'content of the ';
	}
	var answer = confirm ('Do you want to delete the ' + param + 'dataset "' + dataname + '"?');
	if (!answer) {
		return;
	}
	document.body.style.cursor = "wait";
	ajax_client.open("DELETE", url, true);
	ajax_client.setRequestHeader("User-agent", "Tagfiler/1.0");
	ajax_client.onreadystatechange = processDelete;
	ajax_client.send(null);
}

/**
 * Callback function to check the delete result
 */
function processDelete() {
	if(ajax_client.readyState == 4) {
		if(ajax_client.status == 200 || ajax_client.status == 404 || ajax_client.status == 204) {
			window.location.reload(true);
		} else {
			var err = ajax_client.getResponseHeader('X-Error-Description');
			var status = 'Status: ' + ajax_client.status + '. ';
			alert(status + (err != null ? decodeURIComponent(err) : ajax_client.responseText));
		}
		document.body.style.cursor = "default";
	}
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
 * Check that the input box is not empty
 * Return True if the text box is not empty and False otherwise
 * Display an alert message if the input text box is empty
 */
function checkInput(id, message) {
	if (document.getElementById(id).value.replace(/^\s*/, "").replace(/\s*$/, "").length == 0) {
    	alert('Please enter the ' + message + '.');
    	return false;
	} else {
    	return true;
	}
}

/**
 * Check that the input form for tag values is not empty
 * Return True if the input form is not empty and False otherwise
 */
function checkQueryValues() {
	var ret = false;
	if (document.getElementById("tagvalues").style.display == 'block') {
		for (var i=0; i < 10; i++) {
			if (document.getElementById('val'+i).value.replace(/^\s*/, "").replace(/\s*$/, "").length > 0) {
				ret = true;
				break;
			}
		}
		if (!ret) {
			alert('Please enter a value for the tag.');
		}
	} else {
		ret = true;
	}
	return ret;
}

/**
 * Set the dropdown list with the available operators for the selected tag
 */
function selectTagOperators() {
	var select_list_field = document.getElementById("tag");
	var select_list_selected_index = select_list_field.selectedIndex;
	var typestr = select_list_field.options[select_list_selected_index].getAttribute("typestr");
	
	select_list_field = document.getElementById("op");
	for (var i=0; i < select_list_field.options.length; i++) {
		if (opArray['id_' + select_list_field.options[i].value].contains(typestr)) {
			// typestr is in the exclude list
			document.getElementById('id_' + select_list_field.options[i].value).style.display = 'none';
		} else {
			document.getElementById('id_' + select_list_field.options[i].value).style.display = 'block';
		}
	}
	
	selectOperatorForm();
}

/**
 * Select the form for the tag values
 */
function selectOperatorForm() {
	var display_value = 'block';
	var select_list_field = document.getElementById("op");
	var select_list_selected_index = select_list_field.selectedIndex;
	var op = select_list_field.options[select_list_selected_index].value;
	if (op == '' || op == ':absent:') {
		// tagged or tag absent
		display_value = 'none';
	}
	
	document.getElementById("tagvalues").style.display = display_value;
}

var datasetStatusPrefix = '<table align="center" ><tr><td><b style="color:green">';
var datasetStatusSuffix = '. Please wait...</b></td></tr></table>';

/**
 * Make html transformations for the NameForm based on the dataset type
 */
function changeNameFormType(op, suffix) {
	document.getElementById('fileName'+suffix).style.display = (document.getElementById('type'+suffix).value == 'file' ? 'inline' : 'none');
	if (op == 'create') {
		if (document.getElementById('type'+suffix).value == 'blank') {
			document.getElementById('namedDataset'+suffix).style.display = 'none';
			document.getElementById('datasetName'+suffix).value = '';
		} else {
			document.getElementById('namedDataset'+suffix).style.display = 'block';
		}
	}
}

/**
 * Validate and make html transformations for the NameForm
 * Return True in case of success and False otherwise
 */
function validateNameForm(op, suffix) {
	if (op == 'create' && document.getElementById('type'+suffix).value != 'blank' && !checkInput('datasetName'+suffix, 'name of the dataset')) {
		return false;
	}
	var type = document.getElementById('type'+suffix).value;
	var fileInput = null;
	if (type == 'file') {
		if (!checkInput('fileName'+suffix, 'file to be uploaded')) {
			return false;
		}
		fileInput = document.getElementById('fileName'+suffix);
	}
	var data_id = '';
	if (op == 'create') {
		data_id = document.getElementById('datasetName'+suffix).value.replace(/^\s*/, "").replace(/\s*$/, "");
		var action = document.NameForm.getAttribute('action');
		if (data_id.length > 0) {
			action += '/name=' + encodeURIComponent(data_id);
		}
		var prefix = '?';
		if (document.getElementById('read users'+suffix).value == '*') {
			action += '?read%20users=*';
			prefix = '&'
		}
		if (document.getElementById('write users'+suffix).value == '*') {
			action += prefix + 'write%20users=*';
			prefix = '&'
		}
		var defaultView = document.getElementById('defaultView'+suffix).value;
		if (defaultView != '') {
			action += prefix + 'default%20view=' + encodeURIComponent(defaultView);
			prefix = '&'
		}
		if (document.getElementById('incomplete'+suffix).checked) {
			action += prefix + 'incomplete';
		}
		document.NameForm.setAttribute('action', action);
	}
	var NameForm = document.getElementById('NameForm'+suffix);
	if (type == 'file') {
		NameForm.setAttribute('enctype', 'multipart/form-data');
	} else {
		NameForm.setAttribute('enctype', 'application/x-www-form-urlencoded');
	}
	var form = document.getElementById('NameForm'+suffix);
	orig_form = document.getElementById('NameForm_div'+suffix);
	form.removeChild(orig_form);
	var statusValue = datasetStatusPrefix;
	if (type == 'file') {
		form.appendChild(fileInput);
		fileInput.style.display = 'none';
		statusValue += 'Uploading file "' + fileInput.value + '"';
	} else {
		var input = document.createElement('input');
		input.setAttribute('type', 'hidden');		
		input.setAttribute('name', 'action');		
		input.setAttribute('id', 'action'+suffix);		
		input.setAttribute('value', 'post');		
		form.appendChild(input);
		if (op == 'create') {
			statusValue += 'Registering ' + (data_id.length > 0 ? '"'+data_id+'" dataset' : 'the blank node');
		} else {
			statusValue += 'Replacing the dataset';
		}
	}
	
	if (suffix.length == 0) {
		document.getElementById('submit'+suffix).style.display = 'none';
	}
	statusValue += datasetStatusSuffix;
	document.getElementById('Copy'+suffix).innerHTML = statusValue;
	
	return true;
}

function notifyFailure(err) {
	alert(err);
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
var hasSize = false;
var ajax_client = null;

if(window.ActiveXObject) {
  ajax_request = new ActiveXObject("Microsoft.XMLHTTP");
  ajax_client = new ActiveXObject("Microsoft.XMLHTTP");
}
else if(window.XMLHttpRequest) {
  ajax_request = new XMLHttpRequest();
  ajax_client = new XMLHttpRequest();
}

if(ajax_request) {
  ajax_request.onreadystatechange = processSessionRequest;
}

var redirectToLogin = false;

function renderTagdefs(home, table) {
    var columns = [];
    var columnmap = {};
    var typedescs = null;
    var cardinality = [];
    cardinality[false] = "0 or 1";
    cardinality[true] = "0 or more";

    var rows = table.getElementsByTagName("tr");
    var headrow = rows[0];

    var headers = headrow.children;
    for (i=0; i<headers.length; i++) {
	columns[i] = headers[i].getAttribute("name");
	columnmap[columns[i]] = i;
	var name = headers[i].getAttribute("name");
	if ( name == "typestr") {
	    typedescs = JSON.parse(decodeURIComponent(headers[i].innerHTML));
	    headers[i].innerHTML = "Tag type";
	}
	else {
	    labels = { "Tag name" : "Tag name",
		       "Owner" : "Owner",
		       "multivalue" : "#&nbsp;Values",
		       "readpolicy" : "Tag readers",
		       "writepolicy" : "Tag writers",
		       "unique" : "Tag unique" };
	    headers[i].innerHTML = labels[headers[i].innerHTML];
	}
    }

    for (i=1; i<rows.length; i++) {
	if ( (rows[i].getAttribute("class") == "tagdef writeok") || (rows[i].getAttribute("class") == "tagdef readonly") ) {
	    var cells = rows[i].children;
	    var namecell = cells[columnmap["tagname"]];
	    var tagname = namecell.innerHTML;
	    namecell.innerHTML = '<a href="' + home + '/file/tagdef=' + encodeURIComponent(tagname) + '">' + tagname + '</a>';
	    var typecell = cells[columnmap["typestr"]];
	    typecell.innerHTML = typedescs[typecell.innerHTML];
	    var cardcell = cells[columnmap["multivalue"]];
	    cardcell.innerHTML = cardinality[cardcell.innerHTML];
	    var ownercell = cells[columnmap["owner"]];
	    var owner = ownercell.innerHTML;
	    var ownerand = "";
	    if (owner != "") {
		ownerand = "\"" + owner + "\" and "
	    }
	    var policy = { "anonymous" : "anyone", 
			   "users" : "authenticated users", 
			   "subject" : "users who can access the subject", 
			   "subjectowner" : "user who owns the subject",
			   "tag" : (ownerand + "users in ACL"),
			   "system" : "internal service" };
	    var readpolcell = cells[columnmap["readpolicy"]];
	    readpolcell.innerHTML = policy[readpolcell.innerHTML];
	    var writepolcell = cells[columnmap["writepolicy"]];
	    writepolcell.innerHTML = policy[writepolcell.innerHTML];

	    if ( rows[i].getAttribute("class") == "tagdef writeok" ) {
		namecell.innerHTML = "<form "
		    + "encoding=\"application/x-www-url-encoded\" "
		    + "action=\"/tagfiler/tagdef\" method=\"post\">"
		    + "<input type=\"hidden\" name=\"tag\" value=\"" + tagname + "\" />"
		    + "<input type=\"hidden\" name=\"action\" value=\"delete\" />"
		    + "<input type=\"submit\" value=\"[X]\" title=\"delete " + tagname + "\" />"
		    + namecell.innerHTML + "</form>";
	    }
	    if ( i % 2 == 1 ) {
		rows[i].className = "tagdef odd";
	    }
	    else {
		rows[i].className = "tagdef even";
	    }
	}
    }
}

var calWindow;
var today;
var cal;
var calDoc;
var MonthName=["January", "February", "March", "April", "May", "June","July", "August", "September", "October", "November", "December"];
var WeekDayName=["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];	
var DaysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

var WeekHeadColor="pink";
var WeekendColor="cyan";
var WeekDayColor="white";
var FontColor="blue";
var TodayColor="yellow";
var DateColor="white";
var YearColor="blue";

function generateCalendar(id)
{
	today = new Date();	
	cal = new Calendar(today);
	cal.id = id;
	calWindow = window.open("", "", "toolbar=0, status=0, menubar=0, fullscreen=no, width=205, height=215, resizable=0, top=200, left=500");
	calDoc = calWindow.document;
	renderCalendar();
}

function renderCalendar()
{
	var calHeader;
	var calData;
	var i;
	var j;
	var selectedMonth;
	var dayCount = 0;
	var firstDay;

	calDoc.open();
	calDoc.writeln("<html><head><title>Date Picker</title>");
	calDoc.writeln("<script>var winMain=window.opener;</script>");
	calDoc.writeln("</head><body link=" + FontColor + " vlink=" + FontColor + "><form name='Calendar'>");

	calHeader = "<table border=1 cellpadding=1 cellspacing=1 width='100%' align=\"center\" valign=\"top\">\n";
	calHeader += "<tr>\n<td colspan='7'><table border=0 width='100%' cellpadding=0 cellspacing=0><tr><td align='left'>\n";
	calHeader += "<select name=\"MonthSelector\" onChange=\"javascript:winMain.cal.switchMonth(selectedIndex);winMain.renderCalendar();\">\n";
	
	for (i=0; i<12; i++)
	{
		if (i == cal.Month)
			selectedMonth = "Selected";
		else
			selectedMonth = "";	
		calHeader += "<option " + selectedMonth + " value >" + MonthName[i] + "\n";
	}

	calHeader += "</select></td>";
	calHeader += "\n<td align='right'><a href=\"javascript:winMain.cal.previousYear();winMain.renderCalendar()\"><b><font color=\"" + YearColor +
		     "\"><</font></b></a><font color=\"" + YearColor + "\" size=2><b> " + cal.Year + 
		     " </b></font><a href=\"javascript:winMain.cal.nextYear();winMain.renderCalendar()\"><b><font color=\"" + YearColor + "\">></font></b></a></td></tr></table></td>\n";	
	calHeader += "</tr>";
	calHeader += "<tr bgcolor=" + WeekHeadColor + ">";
	
	for (i=0; i<7; i++)
	{
		calHeader += "<td align='center'><font size='2'>" + WeekDayName[i].substr(0,2) + "</font></td>";
	}

	calHeader += "</tr>";	
	calDoc.write(calHeader);
	
	calDate = new Date(cal.Year, cal.Month);
	calDate.setDate(1);
	firstDay = calDate.getDay();
	calData = "<tr>";

	for (i=0; i<firstDay; i++)
	{
		calData += generateCell();
		dayCount++;
	}

	for (j=1; j<=cal.monthDays(); j++)
	{
		var cellData;
		dayCount++;
		if ((j == today.getDate()) && (cal.Month == today.getMonth()) && (cal.Year == today.getFullYear()))
			cellData = generateCell(j, true, TodayColor);
		else
		{
			if (j == cal.Date)
			{
				cellData = generateCell(j, true, DateColor);
			}
			else
			{	 
				if (dayCount%7 == 0 || (dayCount + 6) % 7 == 0)
					cellData = generateCell(j, false, WeekendColor);
				else
					cellData = generateCell(j, null, WeekDayColor);
			}		
		}						
		calData += cellData;

		if((dayCount % 7 == 0) && (j < cal.monthDays()))
		{
			calData += "</tr>\n<tr>";
		}
	}

	calDoc.writeln(calData);	
	calDoc.writeln("\n</table>");
	calDoc.writeln("</form></body></html>");
	calDoc.close();
}

function generateCell(cellValue, cellHighLight, cellColor)
{
	var value;
	var cellStr;
	var color;
	var highLight1;
	var highLight2;
	
	if (cellValue == null)
		value = "";
	else
		value = cellValue;
	
	if (cellColor != null)
		color = "bgcolor=\"" + cellColor + "\"";
	else
		color = "";	
	if ((cellHighLight != null) && cellHighLight)
	{
		highLight1 = "color='red'><b>";
		highLight2 = "</b>";
	}
	else
	{
		highLight1 = ">"; 
		highLight2 = "";
	}
	
	cellStr = "<td " + color + " width=20 align='center'><font size='2'" + highLight1 + "<a href=\"javascript:winMain.document.getElementById('" + cal.id + "').value='" +
		   cal.dateFormat(value) + "';window.close();\">" + value + "</a>" + highLight2 + "</font></td>";

	return cellStr;
}


function Calendar()
{
	this.Date = today.getDate();
	this.Month = today.getMonth();
	this.Year = today.getFullYear();
}

function nextYear()
{
	cal.Year++;
}
Calendar.prototype.nextYear = nextYear;

function previousYear()
{	
	cal.Year--;
}
Calendar.prototype.previousYear = previousYear;
	
function switchMonth(month)
{
	cal.Month = month;
}
Calendar.prototype.switchMonth = switchMonth;

function monthDays()
{
	if (cal.isLeapYear())
	{
		DaysInMonth[1] = 29;
	}
	
	return DaysInMonth[cal.Month];	
}
Calendar.prototype.monthDays = monthDays;

function isLeapYear()
{
	if (cal.Year % 4 == 0)
	{
		if ((cal.Year % 100 == 0) && cal.Year % 400 != 0)
		{
			return false;
		}
		else
		{
			return true;
		}
	}
	else
	{
		return false;
	}
}
Calendar.prototype.isLeapYear = isLeapYear;

function dateFormat(date)
{
		return (cal.Year + "-" + (cal.Month+1) + "-" + date);
}
Calendar.prototype.dateFormat = dateFormat;	

var MAX_RETRIES = 10;
var AJAX_TIMEOUT = 300000;

var tagSelectOptions = new Object();
var typedefSelectValues = null;
var typedefTagrefs = null;

function handleError(jqXHR, textStatus, errorThrown, count) {
	var retry = false;
	var msg = '';
	var err = jqXHR.status;
	if (err != null) {
		msg += 'Status: ' + err + '\n';
	}
	err = jqXHR.responseText;
	if (err != null) {
		msg += 'ResponseText: ' + err + '\n';
	}
	err = jqXHR.getResponseHeader('X-Error-Description');
	if (err != null) {
		msg += 'X-Error-Description: ' + decodeURIComponent(err) + '\n';
	}
	if (textStatus != null) {
		msg += 'TextStatus: ' + textStatus + '\n';
	}
	if (errorThrown != null) {
		msg += 'ErrorThrown: ' + errorThrown + '\n';
	}
	switch(jqXHR.status) {
	case 0:		// client timeout
	case 408:	// server timeout
	case 503:	// Service Unavailable
	case 504:	// Gateway Timeout
		retry = true;
	}
	
	if (!retry || count > MAX_RETRIES) {
		alert(msg);
	}
	
	return retry;
}

function initTypedefSelectValues(home, webauthnhome, typestr, id, pattern, count) {
	var url = home + '/query/' + encodeURIComponent('typedef values') + '(typedef)?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: (count <= MAX_RETRIES ? true : false),
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			typedefSelectValues = new Array();
			$.each(data, function(i, object) {
				typedefSelectValues.push(object['typedef']);
			});
			initTypedefTagrefs(home, webauthnhome, typestr, id, pattern, count)
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){initTypedefSelectValues(home, webauthnhome, typestr, id, pattern, count)}, delay);
			}
		}
	});
}

function initTypedefTagrefs(home, webauthnhome, typestr, id, pattern, count) {
	var url = home + '/query/' + encodeURIComponent('typedef tagref') + '(typedef;' + encodeURIComponent('typedef tagref') + ')?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: (count <= MAX_RETRIES ? true : false),
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			typedefTagrefs = new Object();
			$.each(data, function(i, object) {
				typedefTagrefs[object['typedef']] = object['typedef tagref'];
			});
			if (tagSelectOptions[typestr] == null) {
				initTagSelectOptions(home, webauthnhome, typestr, id, pattern, count);
			} else {
				appendOptions(typestr, id, pattern);
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){initTypedefTagrefs(home, webauthnhome, typestr, id, pattern, count)}, delay);
			}
		}
	});
}

function initTagSelectOptions(home, webauthnhome, typestr, id, pattern, count) {
	tagSelectOptions[typestr] = new Array();
	if (typestr == 'role') {
		url = webauthnhome + '/role';
	} else if (typedefSelectValues.contains(typestr)) {
		url = home + '/tags/typedef=' + encodeURIComponent(typestr) + '(' + encodeURIComponent('typedef values') + ')?limit=none';
	} else if (typedefTagrefs[typestr] != null) {
		url = home + '/query/' + encodeURIComponent(typedefTagrefs[typestr]) + '(' + encodeURIComponent(typedefTagrefs[typestr]) + ')' + encodeURIComponent(typedefTagrefs[typestr]) + '?limit=none';
	} else {
		alert('Invalid typestr: "' + typestr + '"');
		return;
	}
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: (count <= MAX_RETRIES ? true : false),
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			$.each(data, function(i, object) {
				if (typestr == 'role') {
					var option = new Object();
					option.value = object;
					option.text = object;
					tagSelectOptions[typestr].push(option);
				} else if (typedefSelectValues.contains(typestr)) {
					$.each(object['typedef values'], function(j, item) {
						var option = new Object();
						var index = item.indexOf(' ');
						if (index != -1) {
							option.value = item.substring(0, index++);
							var description = item.substr(index);
							if (description != option.value) {
								option.text = option.value + ' (' + item.substr(index) + ')';
							} else {
								option.text = option.value;
							}
						} else {
							option.value = item;
							option.text = item;
						}
						tagSelectOptions[typestr].push(option);
					});
				} else {
					var option = new Object();
					option.value = object[typedefTagrefs[typestr]];
					option.text = object[typedefTagrefs[typestr]];
					tagSelectOptions[typestr].push(option);
				}
			});
			appendOptions(typestr, id, pattern);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){initTagSelectOptions(home, webauthnhome, typestr, id, pattern, count)}, delay);
			} else {
				delete tagSelectOptions[typestr];
			}
		}
	});
}

function chooseOptions(home, webauthnhome, typestr, id, count) {
	if (count == null) {
		count = 0;
	}
	var pattern = '';
	if (typestr == 'rolepat') {
		pattern = '*';
		typestr = 'role'
	}
	if (typedefSelectValues == null) {
		initTypedefSelectValues(home, webauthnhome, typestr, id, pattern, count);
	} else if (tagSelectOptions[typestr] == null) {
		initTagSelectOptions(home, webauthnhome, typestr, id, pattern, count);
	} else {
		appendOptions(typestr, id, pattern);
	}
}

function appendOptions(typestr, id, pattern) {
	document.getElementById(id).removeAttribute('onclick');
	var select = $(document.getElementById(id));
	if (pattern != '') {
		var option = $('<option>');
		option.text(pattern);
		option.attr('value', pattern);
		select.append(option);
	}
	$.each(tagSelectOptions[typestr], function(i, value) {
		var option = $('<option>');
		option.text(value.text);
		option.attr('value', value.value);
		select.append(option);
	});
}

var typedefTags = null;

function initTypedefTags(home, id, count) {
	var url = home + '/query/typedef(typedef;' + encodeURIComponent('typedef description') + ')' + encodeURIComponent('typedef description') + '?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			typedefTags = new Array();
			$.each(data, function(i, object) {
				typedefTags.push(object);
			});
			appendTypedefs(id);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){initTypedefTags(home, id, count)}, delay);
			}
		}
	});
}

function chooseTypedefs(home, id) {
	if (typedefTags == null) {
		initTypedefTags(home, id, 0);
	} else {
		appendTypedefs(id);
	}
}

function appendTypedefs(id) {
	document.getElementById(id).removeAttribute('onclick');
	var select = $(document.getElementById(id));
	$.each(typedefTags, function(i, item) {
		if (item['typedef'] != 'empty') {
			var option = $('<option>');
			option.text(item['typedef description']);
			option.attr('value', item['typedef']);
			select.append(option);
		}
	});
}

var HOME;
var USER;
var WEBAUTHNHOME;
var ROW_COUNTER;
var VAL_COUNTER;
var PREVIEW_COUNTER;
var ROW_TAGS_COUNTER;
var ROW_SORTED_COUNTER;
var availableTags = null;
var availableTagdefs = null;
var allTagdefs = null;
var availableViews = null;
var ops = new Object();
var opsExcludeTypes = new Object();
var typedefSubjects = null;

var headerTags = ['name', 'id'];
var resultColumns = [];
var viewListTags = new Object();
var disableAjaxAlert = false;
var sortColumnsArray = new Array();
var editInProgress = false;
var saveSearchConstraint;
var tagToMove = null;

var confirmQueryEditDialog = null;
var confirmAddTagDialog = null;
var confirmAddMultipleTagsDialog = null;

var dragAndDropBox;
var tipBox;

var movePageX;

var SELECT_LIMIT = 15;
var select_tags;

function appendTagValuesOptions(tag, id) {
	var select = $(document.getElementById(id));
	$.each(select_tags[tag], function(i, value) {
		var option = $('<option>');
		option.text(value);
		option.attr('value', value);
		select.append(option);
	});
}

function DisplayDragAndDropBox(e) {
	dragAndDropBox.css('left', String(parseInt(e.pageX) + 'px'));
	dragAndDropBox.css('top', String(parseInt(e.pageY) + 'px'));
	dragAndDropBox.html(tagToMove);
	dragAndDropBox.css('display', 'block');
	var header = $('#Query_Preview_header');
	var minX = parseInt(header.offset().left);
	var value = header.css('width');
	var length = value.length - 2;
	var maxX = minX + parseInt(value.substr(0, length));
	var x = e.pageX;
	if (x <= maxX) {
		if (e.pageX != movePageX) {
			if (e.pageX > movePageX) {
				// right move
				if (e.clientX > $(window).width() * 2 / 3) {
					var dx = Math.ceil(($(window).width() - e.clientX) / 4);
					window.scrollBy(dx, 0);
					movePageX = e.pageX;
				}
			} else if (e.pageX < movePageX) {
				// left move
				if (e.clientX < $(window).width() / 4) {
					var dx = Math.floor(- (e.clientX / 4));
					window.scrollBy(dx, 0);
					movePageX = e.pageX;
				}
			}
		}
	}
}

function HideDragAndDropBox() {
	dragAndDropBox.css('display', 'none');
}

function DisplayTipBox(e, content) {
	if (tagToMove != null) {
		return;
	}
	tipBox.html(content);
	var value = tipBox.css('width');
	var length = value.length - 2;
	var dx = parseInt(value.substr(0, length)) + 30;
	dx = (e.clientX >= $(window).width() * 2 / 3) ? -dx : 0;
	tipBox.css('left', String(parseInt(e.pageX + dx) + 'px'));
	tipBox.css('top', String(parseInt(e.pageY - 50) + 'px'));
	tipBox.css('display', 'block');
}

function HideTipBox() {
	tipBox.css('display', 'none');
}

function copyColumn(e, column, id) {
	e.preventDefault();
	tagToMove = column;
	movePageX = e.pageX;
}

function interchangeColumns(index1, index2, append) {
	var thead = $('#Query_Preview_header');
	for (var i=0; i < thead.children().length; i++) {
		var tr = getChild(thead, i+1);
		var col1 = getChild(tr, index1 + 1);
		var col2 = getChild(tr, index2 + 1);
		if (append) {
			col1.insertAfter(col2);
		} else {
			col1.insertBefore(col2);
		}
	}
	var tbody = $('#Query_Preview_tbody');
	for (var i=0; i < tbody.children().length; i++) {
		var tr = getChild(tbody, i+1);
		if (tr.css('display') == 'none') {
			break;
		}
		var col1 = getChild(tr, index1 + 1);
		var col2 = getChild(tr, index2 + 1);
		if (append) {
			col1.insertAfter(col2);
		} else {
			col1.insertBefore(col2);
		}
	}
}

function dropColumn(e, tag, id, append) {
	if (tagToMove == null) {
		return;
	}
	e.preventDefault();
	HideDragAndDropBox();
	if (tagToMove == tag) {
		tagToMove = null;
		return;
	}
	var index = -1;
	$.each(resultColumns, function(i, column) {
		if (column == tagToMove) {
			index = i;
			return false;
		}
	});
	var tagToMoveIndex = index;
	index = -1;
	$.each(resultColumns, function(i, column) {
		if (column == tag) {
			index = i;
			return false;
		}
	});
	var tagToDropIndex = index;
	resultColumns.splice(tagToMoveIndex, 1);
	index = -1;
	$.each(resultColumns, function(i, column) {
		if (column == tag) {
			index = i;
			return false;
		}
	});
	if (!append) {
		resultColumns.splice(index, 0, tagToMove);
	} else {
		resultColumns.push(tagToMove);
	}

	tagToMove = null;
	interchangeColumns(tagToMoveIndex, tagToDropIndex, append);
}

function str(value) {
	return '\'' + value + '\'';
}

function makeId() {
	var parts = new Array();
	for( var i=0; i < arguments.length; i++ ) {
		parts.push(arguments[i]);
	}
	return parts.join('_');
}

function makeFunction() {
	var parts = new Array();
	for( var i=1; i < arguments.length; i++ ) {
		parts.push(arguments[i]);
	}
	return arguments[0] + '(' + parts.join(', ') + ');';
}

function makeAttributes() {
	var elem = arguments[0];
	for( var i=1; i < arguments.length; i+=2 ) {
		elem.attr(arguments[i], arguments[i+1]);
	}
}

function getChild(item, index) {
	return item.children(':nth-child(' + index + ')');
}

function getColumnOver(e) {
	var ret = new Object();
	var header = $('#Query_Preview_header');
	var minY = parseInt(header.offset().top);
	var minX = parseInt(header.offset().left);
	var value = header.css('height');
	var length = value.length - 2;
	var maxY = minY + parseInt(value.substr(0, length));
	value = header.css('width');
	length = value.length - 2;
	var maxX = minX + parseInt(value.substr(0, length));
	var x = parseInt(e.pageX);
	var y = parseInt(e.pageY);
	var tr = getChild(header, 2);
	if (y < minY || y > maxY) {
		$('td.highlighted').removeClass('highlighted');
	} else if (x <= minX) {
		var children = tr.children();
		var tag = resultColumns[0];
		var th = $(children[0]).find('th');
		var id = th.attr('id');
		ret['tag'] = tag;
		ret['id'] = id;
		ret['append'] = false;
		ret['index'] = 0;
		var trs = $('.tablerow');
		$('td.highlighted').removeClass('highlighted');
		$('td:nth-child('+1+')', trs).addClass('highlighted');
	} else if (x >= maxX) {
		var children = tr.children();
		var i = resultColumns.length;
		var tag = resultColumns[i-1];
		var th = $(children[i-1]).find('th');
		var id = th.attr('id');
		ret['tag'] = tag;
		ret['id'] = id;
		ret['append'] = true;
		ret['index'] = i - 1;
	} else {
		var children = tr.children();
		for (var i=1; i <= resultColumns.length; i++) {
			var j = (i < resultColumns.length) ? i : (i-1);
			var left = parseInt($(children[j]).offset().left);
			if (left >= x || i == resultColumns.length) {
				j = (j == i) ? i - 1 : j;
				var append = false;
				if (i == resultColumns.length) {
					if (x >= (maxX + left)/2) {
						append = true;
					}
				}
				var tag = resultColumns[j];
				var th = $(children[j]).find('th');
				var id = th.attr('id');
				ret['tag'] = tag;
				ret['id'] = id;
				ret['append'] = append;
				ret['index'] = j;
				var trs = $('.tablerow');
				$('td.highlighted').removeClass('highlighted');
				if (!append) {
					$('td:nth-child('+(j+1)+')', trs).addClass('highlighted');
				}
				break;
			}
		}
	}
	return ret;
}

function initPSOC(home, user, webauthnhome, basepath, querypath) {
	expiration_warning = false;
	HOME = home;
	USER = user;
	WEBAUTHNHOME = webauthnhome;
	ROW_COUNTER = 0;
	VAL_COUNTER = 0;
	ROW_TAGS_COUNTER = 0;
	ROW_SORTED_COUNTER = 0;
	PREVIEW_COUNTER = 0;
	ENABLE_ROW_HIGHLIGHT = true;
	loadTypedefs();
	//var t = $.parseJSON( querypath );
	
	$(document).mousemove(function(e){
		if (tagToMove == null) {
			return;
		}
		getColumnOver(e);
		DisplayDragAndDropBox(e);
	});
	$(document).mouseup(function(e) {
		var ret = getColumnOver(e);
		if (ret['tag'] == null) {
			HideDragAndDropBox();
			tagToMove = null;
		} else {
			dropColumn(e, ret['tag'], ret['id'], ret['append']);
		}
	});

	// get the default view
	/*
	var url = new String(window.location);
	var default_view = null;
	url = url.replace('/file/', '/tags/') + '(' + encodeURIComponent('default view') + ')';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			default_view = data[0]['default view'];
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
		}
	});
	if (default_view == null) {
		default_view = 'default';
	}
	*/
	default_view = 'default';
	// build the result columns from the header tags + the view tags
	setViewTags(default_view);
	$.each(viewListTags[default_view], function(i, tag) {
		if (!resultColumns.contains(tag)) {
			resultColumns.unshift(tag);
		}
	});
	resultColumns = resultColumns.concat(headerTags);
	$('#customizedViewDiv').css('display', '');
	confirmAddTagDialog = $('#customizedViewDiv');
	confirmAddTagDialog.dialog({
		autoOpen: false,
		title: 'Add a column',
		buttons: {
			"Cancel": function() {
					$(this).dialog('close');
				},
			"Add to query": function() {
					addToListColumns('customizedViewSelect');
					$(this).dialog('close');
				}
		},
		draggable: true,
		position: 'top',
		height: 250,
		modal: false,
		resizable: true,
		width: 450,
	});
	$('#selectViewDiv').css('display', '');
	confirmAddMultipleTagsDialog = $('#selectViewDiv');
	confirmAddMultipleTagsDialog.dialog({
		autoOpen: false,
		title: 'Add columns from a view',
		buttons: {
			"Cancel": function() {
					$(this).dialog('close');
				},
			"Add to query": function() {
					addViewToListColumns('selectViews');
					$(this).dialog('close');
				}
		},
		draggable: true,
		position: 'top',
		height: 250,
		modal: false,
		resizable: true,
		width: 450,
	});
	dragAndDropBox = $('#DragAndDropBox');
	tipBox = $('#TipBox');
	showPreview();
}

function loadTypedefs() {
	var url = HOME + '/query/typedef(typedef;' + encodeURIComponent('typedef values') + ';' +encodeURIComponent('typedef dbtype') + ';' +encodeURIComponent('typedef tagref') + ')?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			typedefSubjects = new Object();
			$.each(data, function(i, object) {
				typedefSubjects[object['typedef']] = object;
			});
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
		}
	});
}

function loadTags() {
	var url = HOME + '/query/tagdef(tagdef;' + encodeURIComponent('tagdef type') + ';' + encodeURIComponent('tagdef multivalue') + ')?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			availableTags = new Object();
			availableTagdefs = new Array();
			allTagdefs = new Object();
			$.each(data, function(i, object) {
				availableTagdefs.push(object['tagdef']);
				availableTags[object['tagdef']] = object['tagdef type'];
				allTagdefs[object['tagdef']] = object;
			});
			availableTagdefs.sort(compareIgnoreCase);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
		}
	});
}

function loadAvailableTags(id) {
	document.getElementById(id).removeAttribute('onclick');
	if (availableTags == null) {
		loadTags();
	}
	var select = $(document.getElementById(id));
	$.each(availableTagdefs, function(i, value) {
		var option = $('<option>');
		option.text(value);
		option.attr('value', value);
		select.append(option);
	});
}

function loadViews() {
	var url = HOME + '/query/view(view)view?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			availableViews = new Array();
			$.each(data, function(i, object) {
				availableViews.push(object.view);
			});
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
		}
	});
}

function loadAvailableViews(id) {
	document.getElementById(id).removeAttribute('onclick');
	if (availableViews == null) {
		loadViews();
	}
	var select = $('#' + id);
	$.each(availableViews, function(i, object) {
		var option = $('<option>');
		option.text(object);
		option.attr('value', object);
		select.append(option);
	});
}

function setViewTags(tag) {
	if (availableTags == null) {
		loadTags();
	}
	if (viewListTags[tag] != null) {
		return;
	}
	var url = HOME + '/query/view=' + encodeURIComponent(tag) + '(' + encodeURIComponent('_cfg_file list tags') + ')' + encodeURIComponent('_cfg_file list tags');
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			viewListTags[tag] = new Array();
			var tags = data[0]['_cfg_file list tags'];
			$.each(tags, function(i, value) {
				viewListTags[tag].push(value);
			});
			viewListTags[tag].reverse();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
		}
	});
}

function addToQueryTable(tableId, tag) {
	var tbody = getChild($('#' + tableId), 2);
	var id = makeId('row', ++ROW_COUNTER);
	var tr = $('<tr>');
	makeAttributes(tr,
					'id', id);
	tr.addClass((tbody.children().length % 2 != 0) ? 'odd' : 'even');
	tr.addClass('gradeA');
	tbody.append(tr);
	var td = $('<td>');
	tr.append(td);
	var img = $('<img>');
	makeAttributes(img,
					'src', HOME + '/static/delete.png',
				    'tag', tag,
					'onclick', makeFunction('deleteRow', str(id)),
					'alt', 'DEL');
	td.append(img);
	td = $('<td>');
	tr.append(td);
	var select = getSelectTagOperator(tag, availableTags[tag]);
	var selId = select.attr('id');
	td.append(select);
	td = $('<td>');
	tr.append(td);
	if (availableTags[tag] != 'empty') {
		var table = $('<table>');
		makeAttributes(table,
					   'id', makeId('table', ROW_COUNTER));
		td.append(table);
		if ($('#' + selId).val() == 'Between') {
			td.attr('colspan', '2');
		}
		td = $('<td>');
		td.css('text-align', 'center');
		td.css('margin-top', '0px');
		td.css('margin-bottom', '0px');
		td.css('padding', '0px');
		tr.append(td);
		var img = $('<img>');
		makeAttributes(img,
						'src', HOME + '/static/new.png',
						'id', makeId('button', ROW_COUNTER),
						'onclick', makeFunction('addNewValue', ROW_COUNTER, str(availableTags[tag]), str(selId), str(tag)),
						'alt', '+');
		td.append(img);
		img.click();
		if ($('#' + selId).val() == 'Between') {
			img.css('display', 'none');
			td.css('display', 'none');
		}
	} else {
		td.attr('colspan', '2');
	}
	setRowsBackground(tableId);
	showPreview();
}

function deleteRow(id) {
	var row = $('#' + id);
	var tableId = row.parent().parent().attr('id');
	row.remove();
	setRowsBackground(tableId);
	showPreview();
}

function deleteValue(id, tableId) {
	var tr = $('#' + id);
	var table = $('#' + tableId);
	var tbody = getChild(table, 1);
	if (tbody.children().length == 1) {
		var td = getChild(tr, 1);
		var input = getChild(td, 2);
		input.val('');
	} else {
		$('#' + id).remove();
	}
	showPreview();
}

function getSelectTagOperator(tag, type) {
	var select = $('<select>');
	var id = makeId('select', ROW_COUNTER);
	makeAttributes(select,
				   'id', id,
				   'name', id,
				   'onchange', makeFunction('displayValuesTable', ROW_COUNTER, str(id), str(tag)));
	if (type != 'empty' && !allTagdefs[tag]['tagdef multivalue']) {
		var option = $('<option>');
		option.text('Between');
		option.attr('value', 'Between');
		select.append(option);
	}
	$.each(ops, function(key, value) {
		if (!opsExcludeTypes[value].contains(type)) {
				var option = $('<option>');
				option.text(key);
				option.attr('value', key);
				select.append(option);
		}
	});
	if (type == 'timestamptz' || type == 'date') {
		select.val('Between');
		select.attr('prevVal', 'Between');
	} else if (type == 'empty') {
		select.val('Tagged');
		select.attr('prevVal', 'Tagged');
	}
	else if (type == 'int8' || type == 'float8' || isSelect(tag, type)) {
		select.val('Equal');
		select.attr('prevVal', 'Equal');
	} else {
		select.val('Regular expression (case insensitive)');
		select.attr('prevVal', 'Regular expression (case insensitive)');
	}
	return select;
}

function isSelect(tag, type) {
	var ret = false;
	if (type == 'role' || 
		type == 'rolepat' || 
		typedefSubjects[type]['typedef values'] != null ||
		typedefSubjects[type]['typedef tagref'] != null ||
		select_tags[tag] != null) {
		
		ret = true;
	}
	return ret;
}

function clearValues(tag, op, oldOp) {
	var ret = false;
	if (op == 'Tagged' || op == 'Tag absent' || op == 'Between' || 
		oldOp == 'Tagged' || oldOp == 'Tag absent' || oldOp == 'Between') {
		ret = true;
	} else {
		var type = availableTags[tag];
		if (isSelect(tag, type)) {
			if (oldOp == 'Equal' || oldOp == 'Not equal') {
				ret = (op != 'Equal' && op != 'Not equal');
			} else if (op == 'Equal' || op == 'Not equal') {
				ret = (oldOp != 'Equal' && oldOp != 'Not equal');
			}
		}
	}
	return ret;
}

function addNewValue(row, type, selectOperatorId, tag) {
	var selVal = $('#' + selectOperatorId).val();
	var valId = makeId('vals', ++VAL_COUNTER);
	var table = $('#' + makeId('table', row));
	table.parent().css('display', '');
	var tr = $('<tr>');
	makeAttributes(tr,
					'id', valId);
	table.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.css('border-width', '0px');
	if (selVal != 'Between') {
		var img = $('<img>');
		makeAttributes(img,
						'src', HOME + '/static/delete.png',
						'onclick', makeFunction('deleteValue', str(valId), str(makeId('table', row))),
						'alt', 'DEL');
		td.append(img);
	}
	if (selVal == 'Between') {
		if (!isSelect(tag, type)) {
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			var input = $('<input>');
			makeAttributes(input,
							'type', 'text',
							'onkeyup', makeFunction('showPreview'));
			td.append(input);
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			td.append('AND');
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			input = $('<input>');
			makeAttributes(input,
							'type', 'text',
							'onkeyup', makeFunction('showPreview'));
			td.append(input);
		} else {
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			var select = $('<select>');
			var selid = makeId('select', 'value', VAL_COUNTER);
			makeAttributes(select,
							'id', selid,
							'onchange', makeFunction('showPreview'));
			var option = $('<option>');
			option.text('Choose a value');
			option.attr('value', '');
			select.append(option);
			td.append(select);
			chooseOptions(HOME, WEBAUTHNHOME, type, selid, MAX_RETRIES + 1);
			td.append('AND');
			select = $('<select>');
			selid = makeId('select', 'value', ++VAL_COUNTER);
			makeAttributes(select,
							'id', selid,
							'onchange', makeFunction('showPreview'));
			option = $('<option>');
			option.text('Choose a value');
			option.attr('value', '');
			select.append(option);
			td.append(select);
			chooseOptions(HOME, WEBAUTHNHOME, type, selid, MAX_RETRIES + 1);
		}
	} else if (!isSelect(tag, type) || (selVal != 'Equal' && selVal != 'Not equal')) {
		td = $('<td>');
		tr.append(td);
		td.css('border-width', '0px');
		var input = $('<input>');
		makeAttributes(input,
						'type', 'text',
						'onkeyup', makeFunction('showPreview'));
		td.append(input);
	} else {
		td = $('<td>');
		tr.append(td);
		td.css('border-width', '0px');
		var select = $('<select>');
		var selid = makeId('select', 'value', VAL_COUNTER);
		makeAttributes(select,
						'id', selid,
						'onchange', makeFunction('showPreview'));
		var option = $('<option>');
		option.text('Choose a value');
		option.attr('value', '');
		select.append(option);
		td.append(select);
		if (select_tags[tag] != null) {
			appendTagValuesOptions(tag, selid);
		} else {
			chooseOptions(HOME, WEBAUTHNHOME, type, selid, MAX_RETRIES + 1);
		}
	}
}

function setRowsBackground(tableId) {
	var table = $('#' + tableId);
	var tbody = getChild(table, 2);
	var odd = false;
	$.each(tbody.children(), function(i, tr) {
		$(tr).removeClass('odd');
		$(tr).removeClass('even');
		$(tr).addClass(odd ? 'odd' : 'even');
		odd = !odd
	});
}

function getQueryTags(tableId) {
	var ret = new Array();
	var tbody = getChild($('#' + tableId), 1);
	$.each(tbody.children(), function(i, tr) {
		ret.push(encodeURIComponent(getChild($(tr), 2).html()));
	});
	if (ret.length == 0) {
		ret = '';
	}
	
	return ret;
}

function encodeURIArray(tags) {
	var ret = new Array();
	for (var i=0; i < tags.length; i++) {
		ret.push(encodeURIComponent(tags[i]));
	}
	return ret;
}

function getQueryUrl(limit, encodedResultColumns, encodedSortedColumns) {
	var retTags = '(' + encodedResultColumns.join(';') + ')';
	var encodedResultColumns = new Array();
	var sortTags = encodedSortedColumns.join(',');
	var latest = '?versions=' + $('#versions').val();
	var query = new Array();
	var divs = $('#queryDiv').children();
	if (confirmQueryEditDialog != null) {
		divs.push(confirmQueryEditDialog);
	}
	$.each(divs, function(k, div) {
		var searchTag = $(div).attr('tag');
		var searchTagId = makeId(searchTag.split(' ').join('_'));
		var divTable = $('#' + makeId(searchTagId, 'searchTable'));
		var divtbody = getChild(divTable, 2);
		var trs = divtbody.children();
		$.each(trs, function(i, tr) {
			// tag column
			var td = getChild($(tr), 1);
			var tag = encodeURIComponent(getChild(td, 1).attr('tag'));
			
			// operator column
			td = getChild($(tr), 2);
			var op = getChild(td, 1).val();
			if (op == 'Between') {
				td = getChild($(tr), 3);
				var table = getChild(td, 1);
				var tbody = getChild(table, 1);
				var tr = getChild(tbody, 1);
				var td = getChild(tr, 2);
				var val1 = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
				td = getChild(tr, 4);
				var val2 = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
				if (val1 != '' && val2 != '') {
					query.push(tag + ':geq:' + val1);
					query.push(tag + ':leq:' + val2);
				}
			} else if (op != 'Tagged' && op != 'Tag absent') {
				// values column
				td = getChild($(tr), 3);
				var table = getChild(td, 1);
				var tbody = getChild(table, 1);
				var values = new Array();
				$.each(tbody.children(), function(j, row) {
					td = getChild($(row), 2);
					var input = getChild(td, 1);
					var val = input.val().replace(/^\s*/, "").replace(/\s*$/, "");
					if (val.length > 0) {
						values.push(encodeURIComponent(val));
					}
				});
				if (values.length > 0) {
					query.push(tag + ops[op] + values.join(','));
				}
			} else {
				query.push(tag + ops[op]);
			}
		});
	});
	var url = '';
	if (query.length > 0) {
		url = query.join(';');
	}
	url = HOME + '/query/' + url + retTags + sortTags + latest + limit;
	return url;
}

function displayValuesTable(row, selId, tag) {
	var oldOp = $('#' + makeId('select', row)).attr('prevVal');
	var op = $('#' + makeId('select', row)).val();
	var clearValuesTable = clearValues(tag, op, oldOp);
	if (clearValuesTable) {
		var table = $('#' + makeId('table', row));
		var tbody = getChild(table, 1);
		if ($('#' + makeId('table', row)).get(0) != null) {
			$.each(tbody.children(), function(i, tr) {
				$(tr).remove();
			});
		}
	}
	if (op == 'Tagged' || op == 'Tag absent') {
		$('#' + makeId('button', row)).parent().prev().attr('colspan', '2');
		$('#' + makeId('button', row)).parent().css('display', 'none');
	} else {
			$('#' + makeId('button', row)).parent().prev().attr('colspan', '1');
			$('#' + makeId('button', row)).parent().css('display', '');
			$('#' + makeId('button', row)).css('display', '');
			if (clearValuesTable) {
				$('#' + makeId('button', row)).click();
			}
			if ($('#' + selId).val() == 'Between') {
				$('#' + makeId('button', row)).css('display', 'none');
			}
	}
	$('#' + makeId('select', row)).attr('prevVal', op);
	showPreview();
}

function addToListColumns(selectId) {
	var column = $('#' + selectId).val();
	confirmAddTagDialog.dialog('close');
	if (!resultColumns.contains(column)) {
		resultColumns.unshift(column);
		showPreview();
	}
}

function deleteTag(tableId, id) {
	$('#' + id).remove();
	ENABLE_ROW_HIGHLIGHT = false;
	showPreview();
}

function showPreview() {
	PREVIEW_COUNTER++;
	showQueryResults('');
}

function showQueryResults(limit) {
	var queryUrl = getQueryUrl(limit, encodeURIArray(resultColumns), encodeURIArray(sortColumnsArray));
	$('#Query_URL').attr('href', queryUrl);
	var totalRows = 0;
	queryUrl = getQueryUrl('&range=count', encodeURIArray(resultColumns), new Array());
	$.ajax({
		url: queryUrl,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
		success: function(data, textStatus, jqXHR) {
			totalRows = data[0]['id'];
			select_tags = new Object();
			if (totalRows > 0) {
				var selectedResults = new Array();
				$.each(data[0], function(tag, value) {
					if (value > 0 && value <= SELECT_LIMIT) {
						selectedResults.push(tag);
					} 
				});
				if (selectedResults.length > 0) {
					queryUrl = getQueryUrl('&range=values', encodeURIArray(selectedResults), new Array());
					$.ajax({
						url: queryUrl,
						headers: {'User-agent': 'Tagfiler/1.0'},
						async: true,
						accepts: {text: 'application/json'},
						dataType: 'json',
						success: function(data, textStatus, jqXHR) {
							$.each(data[0], function(tag, values) {
								select_tags[tag] = values;
							});
							showQueryResultsTable(limit, totalRows);
						},
						error: function(jqXHR, textStatus, errorThrown) {
							if (!disableAjaxAlert) {
								handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
							}
						}
					});
				} else {
					showQueryResultsTable(limit, totalRows);
				}
			} else {
				showQueryResultsTable(limit, totalRows);
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (!disableAjaxAlert) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
			}
		}
	});
}

function showQueryResultsTable(limit, totalRows) {
	var previewRows = 0;
	var queryUrl = getQueryUrl(limit == '' ? '&limit=15' : limit, encodeURIArray(resultColumns), encodeURIArray(sortColumnsArray));
	var queryPreview = $('#Query_Preview');
	var table = getChild(queryPreview, 1);
	if (table.get(0) == null) {
		table = $('<table>');
		table.addClass('display');
		makeAttributes(table,
						'border', '0',
						'cellpadding', '0',
						'cellspacing', '0');
		queryPreview.append(table);
		var thead = $('<thead>');
		table.append(thead);
		makeAttributes(thead,
						'id', 'Query_Preview_header');
		var tr = $('<tr>');
		thead.append(tr);
		tr = $('<tr>');
		thead.append(tr);
		tr = $('<tr>');
		thead.append(tr);
		var tbody = $('<tbody>');
		makeAttributes(tbody,
						'id', 'Query_Preview_tbody');
		table.append(tbody);
		var tfoot = $('<tfoot>');
		makeAttributes(tfoot,
						'id', 'Query_Preview_tfoot');
		table.append(tfoot);
		tr = $('<tr>');
		tr.addClass('topborder');
		tfoot.append(tr);
	}

	// build the table header
	var thead = getChild(table, 1);
	var tfoot = getChild(table, 3);
	var tr1 = getChild(thead, 1);
	var tr2 = getChild(thead, 2);
	var tr3 = getChild(thead, 3);
	var trfoot = getChild(tfoot, 1);
	var columnLimit = 0;
	$.each(resultColumns, function(i, column) {
		columnLimit = i + 1;
		var tagId = column.split(' ').join('_');
		var thId = makeId(tagId, 'th', PREVIEW_COUNTER);
		var td = getChild(tr1, i+1);
		if (td.get(0) == null) {
			var td = $('<td>');
			tr1.append(td);
			var topDiv = $('<div>');
			topDiv.attr('ALIGN', 'RIGHT');
			td.append(topDiv);
			var toolbarTable = $('<table>');
			topDiv.append(toolbarTable);
			var toolbarTr = $('<tr>');
			toolbarTable.append(toolbarTr);
			var toolbarTd = $('<td>');
			toolbarTr.append(toolbarTd);
			toolbarTd = $('<td>');
			toolbarTr.append(toolbarTd);
			var img = $('<img>');
			img.addClass('tablecolumnsort');
			makeAttributes(img,
							'src', HOME + '/static/bullet_arrow_up.png',
							'alt', 'Sort');
			toolbarTd.append(img);
			toolbarTd = $('<td>');
			toolbarTr.append(toolbarTd);
			img = $('<img>');
			img.addClass('tablecolumnundelete');
			makeAttributes(img,
							'src', HOME + '/static/delete.png',
							'alt', 'DEL');
			toolbarTd.append(img);
			var th = $('<th>');
			tr2.append(th);
			var a = $('<a>');
			a.addClass('tableheadercell');
			th.append(a);
			
			td = $('<td>');
			tr3.append(td);
			var divConstraint = $('<div>');
			td.append(divConstraint);
			
			th = $('<th>');
			trfoot.append(th);
			th.html('&nbsp;');
		}
		var td1 = getChild(tr1, i+1);
		var td2 = getChild(tr2, i+1);
		var td3 = getChild(tr3, i+1);
		var tdfoot = getChild(trfoot, i+1);
		td1.css('display', '');
		td2.css('display', '');
		td3.css('display', '');
		tdfoot.css('display', '');
		td2.attr('onmousedown', makeFunction('copyColumn', 'event', str(column), str(thId)));
		td2.attr('onmouseup', makeFunction('dropColumn', 'event', str(column), str(thId), false));
		
		var topDiv = getChild(td1, 1);
		var toolbarTable = getChild(topDiv, 1);
		var toolbarTbody = getChild(toolbarTable, 1);
		var toolbarTr = getChild(toolbarTbody, 1);
		var toolbarTd = getChild(toolbarTr, 1);
		var columSortId = makeId('sort', column.split(' ').join('_'), PREVIEW_COUNTER);
		toolbarTd.attr('id', columSortId);
		var sortValue = getSortOrder(column);
		toolbarTd.html(sortValue);
		toolbarTd = getChild(toolbarTr, 2);
		var img = getChild(toolbarTd, 1);
		img.css('display', '');
		img.attr('id', makeId('arrow_up', column.split(' ').join('_'), PREVIEW_COUNTER));
		img.attr('tag', column);
		img.attr('onclick', makeFunction('sortColumn', str(column), str(columSortId), PREVIEW_COUNTER, (sortValue == ''), true));
		$('#' + columSortId).unbind('mouseenter mouseleave');
		if (sortValue != '') {
			setSortTipBox(columSortId, parseInt(sortValue));
		}
		toolbarTd = getChild(toolbarTr, 3);
		img = getChild(toolbarTd, 1);
		img.attr('tag', column);
		img.attr('onclick', makeFunction('deleteColumn', str(column)));
		
		var th = td2;
		th.attr('id', thId);
		var a = getChild(th, 1);
		a.attr('href', makeFunction('javascript:editQuery', str(column)));
		a.html(column);
		
		var divConstraint = getChild(td3, 1);
		divConstraint.css('white-space', 'nowrap');
		divConstraint.attr('id', makeId('constraint', column.split(' ').join('_'), PREVIEW_COUNTER));
		divConstraint.html('');
		var searchDisplay = $('#' +makeId('queryDiv', column.split(' ').join('_')));
		if (searchDisplay.get(0) != null) {
			var constraint = getTagSearchDisplay(searchDisplay);
			divConstraint.append(constraint);
		}
	});
	var columnLength = tr1.children().length;
	for (var i=columnLimit; i < columnLength; i++) {
		var td = getChild(tr1, i+1);
		if (td.css('display') == 'none') {
			break;
		}
		td.css('display', 'none');
		td = getChild(tr2, i+1);
		td.css('display', 'none');
		td = getChild(tr3, i+1);
		td.css('display', 'none');
		td = getChild(trfoot, i+1);
		td.css('display', 'none');
	}
	$.ajax({
		url: queryUrl,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
		success: function(data, textStatus, jqXHR) {
			var rowLimit = 0;
			previewRows = data.length;
			var odd = false;
			var tbody = getChild(table, 2);
			$.each(data, function(i, row) {
				rowLimit = i + 1;
				var tr = getChild(tbody, i+1);
				if (tr.get(0) == null) {
					tr = $('<tr>');
					tbody.append(tr);
					tr.addClass(odd ? 'odd' : 'even');
					tr.addClass('gradeA');
					tr.addClass('tablerow');
					if (i == 0) {
						tr.addClass('topborder');
					}
				}
				tr.css('display', '');
				odd = !odd;
				$.each(resultColumns, function(j, column) {
					var td = getChild(tr, j+1);
					if (td.get(0) == null) {
						td = $('<td>');
						td.addClass('tablecell');
						tr.append(td);
					}
					td.css('display', '');
					td.removeClass();
					td.addClass(column.replace(/ /g, ''));
					td.addClass('tablecell');
					td.html('');
					if (row[column] != null) {
						if (!allTagdefs[column]['tagdef multivalue']) {
							if (row[column] === true) {
								td.html('is set');
							} else if (row[column] === false) {
								td.html('not set');
							} else {
								if (column == 'id') {
									var a = $('<a>');
									td.append(a);
									makeAttributes(a,
												   'href', HOME + '/tags/id=' + row[column]);
									a.html(row[column]);
								} else if (column == 'name') {
									var a = $('<a>');
									td.append(a);
									makeAttributes(a,
												   'href', HOME + '/tags/name=' + encodeSafeURIComponent(row[column]));
									a.html(row[column]);
								} else if (column == 'url') {
									var a = $('<a>');
									td.append(a);
									makeAttributes(a,
												   'href', row[column]);
									a.html(row[column]);
								} else {
									td.html(htmlEscape(row[column]));
								}
							}
						} else {
							td.html(row[column].join('<br/>'));
						}
					}
				});
				for (var k=columnLimit; k < columnLength; k++) {
					var td = getChild(tr, k+1);
					if (td.css('display') == 'none') {
						break;
					}
					td.css('display', 'none');
				}
			});
			var b = $('#ViewResults');
			b.html('');
			if (previewRows == 0) {
				b.html('There are no results to list with your current query.');
			} else if (previewRows < totalRows) {
				b.append('Showing only ' + previewRows + ' of ');
				var a = $('<a>');
				makeAttributes(a,
								'href', makeFunction('javascript:showQueryResults', str('&limit=none')));
				a.html('' + totalRows + ' results.');
				b.append(a);
			} else {
				b.html('Showing all ' + previewRows + ' results.');
			}
			var tableLength = tbody.children().length;
			for (var i=rowLimit; i < tableLength; i++) {
				var tr = getChild(tbody, i+1);
				if (tr.css('display') == 'none') {
					break;
				}
				tr.css('display', 'none');
			}
			$('.tablecell').hover( function() {
				var iCol = $('td', this.parentNode).index(this) % resultColumns.length;
				var trs = $('.tablerow');
				$('td:nth-child('+(iCol+1)+')', trs).addClass('highlighted');
			}, function() {
				$('td.highlighted').removeClass('highlighted');
			});
			$('.tableheadercell').hover( function(e) {
				var iCol = $('th', this.parentNode.parentNode).index(this.parentNode) % resultColumns.length;;
				var trs = $('.tablerow');
				$('td:nth-child('+(iCol+1)+')', trs).addClass('highlighted');
				DisplayTipBox(e, 'Click to edit');
			}, function() {
				if (tagToMove == null) {
					$('td.highlighted').removeClass('highlighted');
				}
				HideTipBox();
			});
			$('.tablecolumnsort').hover( function(e) {
				DisplayTipBox(e, 'Sort column');
			}, function() {
				HideTipBox();
			});
			$('.tablecolumnundelete').hover( function(e) {
				DisplayTipBox(e, 'Delete column');
			}, function() {
				HideTipBox();
			});
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (!disableAjaxAlert) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1);
			}
		}
	});
}

function htmlEscape(str) {
    return String(str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
}

function setSortTipBox(id, index) {
	var content;
	switch(index) {
		case 1:
			content = 'First sorted column';
			break;
		case 2:
			content = 'Second sorted column';
			break;
		default:
			content = 'n-th sorted column';
			break;
	}
	$('#' + id).hover( function(e) {
		DisplayTipBox(e, content);
	}, function() {
		HideTipBox();
	});
}

function sortColumn(column, id, count, sort) {
	if (sort) {
		sortColumnsArray.push(column);
		var length = sortColumnsArray.length;
		$('#' + id).html('' + length);
		var content;
		switch(length) {
			case 1:
				content = 'First sorted column';
				break;
			case 2:
				content = 'Second sorted column';
				break;
			default:
				content = 'n-th sorted column';
				break;
		}
		$('#' + id).hover( function(e) {
			DisplayTipBox(e, content);
		}, function() {
			HideTipBox();
		});
	} else {
		stopSortColumn(column, id, count);
		$('#' + id).unbind('mouseenter mouseleave');
	}
	showPreview();
}

function stopSortColumn(tag, id, count) {
	var index = -1;
	$.each(sortColumnsArray, function(i, column) {
		if (column == tag) {
			index = i;
			return false;
		}
	});
	sortColumnsArray.splice(index, 1);
	$('#' + id).html('');
	$.each(sortColumnsArray, function(i, column) {
		var id = makeId('sort', column.split(' ').join('_'), count);
		var val = parseInt($('#' + id).html());
		if (val > index) {
			$('#' + id).html('' + --val);
			var content = null;
			switch(val) {
				case 1:
					content = 'First sorted column';
					break;
				case 2:
					content = 'Second sorted column';
					break;
			}
			if (content != null) {
				$('#' + id).hover( function(e) {
					DisplayTipBox(e, content);
				}, function() {
					HideTipBox();
				});
			}
		}
	});
}

function getSortOrder(tag) {
	var ret = '';
	$.each(sortColumnsArray, function(i, column) {
		if (column == tag) {
			ret += (i + 1);
			return false;
		}
	});
	return ret;
}

function addTagToQuery() {
	confirmAddTagDialog.dialog('open');
	$('#customizedViewSelect').val('');
}

function addViewTagsToQuery() {
	confirmAddMultipleTagsDialog.dialog('open');
	$('#selectViews').val('');
}

function addViewToListColumns(id) {
	var val = $('#' + id).val();
	setViewTags(val);
	var preview = false; 
	$.each(viewListTags[val], function(i, tag) {
		if (!resultColumns.contains(tag)) {
			resultColumns.unshift(tag);
			preview = true;
		}
	});
	if (preview) {
		showPreview();
	}
}

function hideColumn(index) {
	var thead = $('#Query_Preview_header');
	for (var i=0; i < thead.children().length; i++) {
		var tr = getChild(thead, i+1);
		var col = getChild(tr, index + 1);
		col.css('display', 'none');
	}
	var tbody = $('#Query_Preview_tbody');
	for (var i=0; i < tbody.children().length; i++) {
		var tr = getChild(tbody, i+1);
		if (tr.css('display') == 'none') {
			break;
		}
		var col = getChild(tr, index + 1);
		col.css('display', 'none');
	}
	var tfoot = $('#Query_Preview_tfoot');
	var tr = getChild(tfoot, 1);
	var col = getChild(tr, resultColumns.length);
	col.css('display', 'none');
}

function deleteColumn(column) {
	$.each(sortColumnsArray, function(i, tag) {
		if (tag == column) {
			sortColumnsArray.splice(i, 1);
			return false;
		}
	});
	var deleteIndex = -1;
	$.each(resultColumns, function(i, tag) {
		if (tag == column) {
			deleteIndex = i;
			return false;
		}
	});
	for (var i=deleteIndex; i < resultColumns.length - 1; i++) {
		interchangeColumns(i+1, i, false);
	}
	hideColumn(resultColumns.length - 1);
	resultColumns.splice(deleteIndex, 1);
}

function encodeSafeURIComponent(value) {
	var ret = encodeURIComponent(value);
	$.each("~!()'", function(i, c) {
		ret = ret.replace(new RegExp('\\' + c, 'g'), escape(c));
	});
	return ret;
}

function editQuery(tag) {
	if (editInProgress) {
		return;
	}
	editInProgress = true;
	disableAjaxAlert = true;
	var tagId = makeId(tag.split(' ').join('_'));
	var div = $('#queryDiv');
	div.css('display', '');
	
	var tagDiv = $('#' + makeId('queryDiv', tagId));
	if (tagDiv.get(0) == null) {
		tagDiv = tagQueryDiv(tag);
		div.append(tagDiv);
	}
	saveSearchConstraint = tagDiv.clone(true, true);
	copySelectOperator(tag);
	var tbody = tagDiv.find('tbody');
	if (tbody.children().length == 0) {
		addToQueryTable(makeId(tagId, 'searchTable'), tag);
	}
	tagDiv.css('display', '');
	confirmQueryEditDialog = tagDiv;
	confirmQueryEditDialog.dialog({
		autoOpen: false,
		title: 'Edit constraint for column "' + tag + '"',
		buttons: {
			"Cancel": function() {
					$(this).dialog('close');
				},
			"Save": function() {
					saveTagQuery(tag);
					$(this).dialog('close');
				}
		},
		position: 'top',
		draggable: true,
		height: 250,
		modal: false,
		resizable: true,
		width: 750,
		beforeClose: function(event, ui) {cancelEdit(tag);}
	});
	confirmQueryEditDialog.dialog('open');
}

function copySelectOperator(tag) {
	var searchTagId = makeId(tag.split(' ').join('_'));
	var divTable = $('#' + makeId(searchTagId, 'searchTable'));
	var divtbody = getChild(divTable, 2);
	var trs = divtbody.children();
	var toDivTable = saveSearchConstraint.find('#' + makeId(searchTagId, 'searchTable'));
	var toDivtbody = getChild(toDivTable, 2);
	$.each(trs, function(i, tr) {
		// operator column
		var td = getChild($(tr), 2);
		var op = getChild(td, 1).val();
		var toTr = getChild(toDivtbody, i+1);
		var toTd = getChild(toTr, 2);
		getChild(toTd, 1).val(op);
		td = getChild($(tr), 3);
		toTd = getChild($(toTr), 3);
		var selects = td.find('select');
		var toSelects = toTd.find('select');
		$.each(selects, function(j, sel) {
			$(toSelects[j]).val($(sel).val());
		});
	});
}

function cancelEdit(tag) {
	if (!editInProgress) {
		confirmQueryEditDialog.remove();
		confirmQueryEditDialog = null;
		return true;
	}
	confirmQueryEditDialog.remove();
	confirmQueryEditDialog = null;
	$('#queryDiv').append(saveSearchConstraint);
	saveTagQuery(tag);
	return true;
}

function saveTagQuery(tag) {
	var tagId = makeId(tag.split(' ').join('_'));
	var div = $('#' + makeId('constraint', tag.split(' ').join('_')));
	div.html('');
	var constraintDiv = getTagSearchDisplay($('#' +makeId('queryDiv', tagId)));
	div.append(constraintDiv);
	$('#' +makeId('queryDiv', tagId)).css('display', 'none');
	disableAjaxAlert = false;
	editInProgress = false;
	if (confirmQueryEditDialog != null) {
		var child = getChild(confirmQueryEditDialog, 1);
		var tagDiv = $('<div>');
		makeAttributes(tagDiv,
					   'id', makeId('queryDiv', tagId),
					   'tag', tag);
		tagDiv.addClass('dialogfont');
		tagDiv.append(child);
		$('#queryDiv').append(tagDiv);
		tagDiv.css('display', 'none');
		confirmQueryEditDialog.remove();
		confirmQueryEditDialog = null;
	}
	$('#queryDiv').css('display', 'none');
	showPreview();
}

function tagQueryDiv(tag) {
	var tagId = makeId(tag.split(' ').join('_'));
	var div = $('<div>');
	makeAttributes(div,
				   'id', makeId('queryDiv', tagId),
				   'tag', tag);
	div.addClass('dialogfont');
	div.css('display', 'none');
	var fieldset = $('<fieldset>');
	div.append(fieldset);
	var a = $('<a>');
	fieldset.append(a);
	makeAttributes(a,
				   'href', makeFunction('javascript:addToQueryTable', str(makeId(tagId, 'searchTable')), str(tag)));
	a.html('New Constraint');
	fieldset.append($('<br>'));
	fieldset.append($('<br>'));
	var table = $('<table>');
	fieldset.append(table);
	table.addClass('display');
	makeAttributes(table,
				   'id', makeId(tagId, 'searchTable'),
					'border', '0',
					'cellpadding', '0',
					'cellspacing', '0');
	var thead = $('<thead>');
	table.append(thead);
	var tr = $('<tr>');
	thead.append(tr);
	var th = $('<th>');
	tr.append(th);
	th.attr('colspan', '2');
	th.html('&nbsp;&nbsp;Operator&nbsp;&nbsp;');
	th = $('<th>');
	tr.append(th);
	th.attr('colspan', '2');
	th.html('&nbsp;&nbsp;Values&nbsp;&nbsp;');
	var tbody = $('<tbody>');
	table.append(tbody);
	return div;
}

function getTagSearchDisplay(div) {
	var query = new Array();
	var searchTag = div.attr('tag');
	var searchTagId = makeId(searchTag.split(' ').join('_'));
	var divTable = $('#' + makeId(searchTagId, 'searchTable'));
	var divtbody = getChild(divTable, 2);
	var trs = divtbody.children();
	$.each(trs, function(i, tr) {
		var td = getChild($(tr), 2);
		var op = getChild(td, 1).val();
		if (op == 'Between') {
			td = getChild($(tr), 3);
			var table = getChild(td, 1);
			var tbody = getChild(table, 1);
			var tr = getChild(tbody, 1);
			var td = getChild(tr, 2);
			var val1 = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
			td = getChild(tr, 4);
			var val2 = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
			if (val1 != '' && val2 != '') {
				query.push('['+ val1 + ', ' + val2 + ']');
			}
		} else if (op != 'Tagged' && op != 'Tag absent') {
			// values column
			td = getChild($(tr), 3);
			var table = getChild(td, 1);
			var tbody = getChild(table, 1);
			var values = new Array();
			$.each(tbody.children(), function(j, row) {
				td = getChild($(row), 2);
				var input = getChild(td, 1);
				var val = input.val().replace(/^\s*/, "").replace(/\s*$/, "");
				if (val.length > 0) {
					values.push(val);
				}
			});
			if (values.length == 1) {
				query.push(ops[op] + ' ' + values.join(', '));
			}
			else if (values.length > 0) {
				query.push(ops[op] + ' {' + values.join(', ') + '}');
			}
		} else {
			query.push(ops[op]);
		}
	});
	var divConstraint = $('<div>');
	divConstraint.attr('ALIGN', 'LEFT');
	var table = $('<table>');
	divConstraint.append(table);
	$.each(query, function(i, val) {
		var tr = $('<tr>');
		table.append(tr);
		var td = $('<td>');
		tr.append(td);
		if (val == '') {
			td.html(':tagged:');
		} else {
			td.html(val);
		}
	});
	makeAttributes(divConstraint,
				   'onclick', makeFunction('editQuery', str(searchTag)));
	return divConstraint;
}

