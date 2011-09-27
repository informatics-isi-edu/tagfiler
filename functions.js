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
	if (op == '' || op == ':not:') {
		// tagged or not tagged
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
	
	document.getElementById('submit'+suffix).style.display = 'none';
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
    cardinality[false] = "0 or one";
    cardinality[true] = "1 or more";

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
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			typedefSelectValues = new Array();
			$.each(data, function(i, object) {
				typedefSelectValues.push(object['typedef']);
			});
			initTypedefTagrefs(home, webauthnhome, typestr, id, pattern, 0)
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
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			typedefTagrefs = new Object();
			$.each(data, function(i, object) {
				typedefTagrefs[object['typedef']] = object['typedef tagref'];
			});
			if (tagSelectOptions[typestr] == null) {
				initTagSelectOptions(home, webauthnhome, typestr, id, pattern, 0);
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
		async: true,
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
							option.text = decodeURIComponent(item.substring(0, index)) + '(' + item.substr(index) + ')';
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

function chooseOptions(home, webauthnhome, typestr, id) {
	var pattern = '';
	if (typestr == 'rolepat') {
		pattern = '*';
		typestr = 'role'
	}
	if (typedefSelectValues == null) {
		initTypedefSelectValues(home, webauthnhome, typestr, id, pattern, 0);
	} else if (tagSelectOptions[typestr] == null) {
		initTagSelectOptions(home, webauthnhome, typestr, id, pattern, 0);
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

