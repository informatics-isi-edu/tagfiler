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

var confirmLogoutDialog;
var warn_window_is_open = false;
var unique_tags = [];

/**
 * Determines identification and dtype of subject based on already probed metadata.
 */
function subject2identifiers(subject) {
    var results = { datapred: "id=" + subject['id'],
                    dataname: "id=" + subject['id'],
                    dtype: 'blank'
                  };

    /* prefer names over raw ID numbers */
    if (subject['vname']) {
		results.datapred = "vname=" + encodeSafeURIComponent(subject['vname']);
		results.dataname = subject['vname'];
    }
    else {
	/* TODO: search a prepared list of unique tagnames;
	   if subject[tagname] is found non-NULL, override defaults and break loop...

	   results.datapred = encodeSafeURIComponent(tagname) + "=" + encodeSafeURIComponent(subject[tagname]);
	   results.dataname = tagname + "=" + subject[tagname];
	   results.dtype = tagname;
	 */
		 $.each(unique_tags, function(i, tagname) {
		 	if (subject[tagname] != null) {
			   results.datapred = encodeSafeURIComponent(tagname) + "=" + encodeSafeURIComponent(subject[tagname]);
			   results.dataname = tagname + "=" + subject[tagname];
			   results.dtype = tagname;
			   return false;
		 	}
		 });
    }

    if (subject['template mode']) {
		results.dtype = 'template';
    }
    else if (subject['url']) {
		results.dtype = 'url';
    }
    else if (subject['bytes']) {
		results.dtype = 'file';
    }

    return results;
}

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
    val = encodeSafeURIComponent(decodeURIComponent(val));
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
    if (node) {
	alert("About to redirect at end of session");
    }
    if (redirectToLogin) {
	window.location='/webauthn/login?referer=' + encodeSafeURIComponent(window.location);
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
      setCookie("webauthn", encodeSafeURIComponent(parts[0] + "|" + until.toGMTString() + "|" + secsremain));

      if (secsremain < 1) {
	  secsremain = 1;
	  log("processSessionRequest: clamping secsremain to 1");
      }	
	      
      if ( secsremain < expiration_warn_mins * 60) {
	  if (!expiration_warning) {
	  	startExtendSessionTimer(1000);
	  	return;
	  }
	  if (((new Date()).getTime() - extend_time) > (expiration_warn_mins * 60 * 1000) && !warn_window_is_open) {
	      log("processSessionRequest: raising warning window");
	      warn_window_is_open = true;
	      confirmLogoutDialog.dialog('open');
	      $('.ui-widget-overlay').css('opacity', 1.0);
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
			action += '/name=' + encodeSafeURIComponent(data_id);
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
			action += prefix + 'default%20view=' + encodeSafeURIComponent(defaultView);
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
var ajax_request = null;
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
	    namecell.innerHTML = '<a href="' + home + '/file/tagdef=' + encodeSafeURIComponent(tagname) + '">' + tagname + '</a>';
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

function handleError(jqXHR, textStatus, errorThrown, count, url) {
	var retry = false;
	
	switch(jqXHR.status) {
	case 0:		// client timeout
	case 408:	// server timeout
	case 503:	// Service Unavailable
	case 504:	// Gateway Timeout
		retry = (count <= MAX_RETRIES);
	}
	
	if (!retry) {
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
		msg += 'URL: ' + url + '\n';
		alert(msg);
		document.body.style.cursor = "default";
	}
	
	return retry;
}

function initTypedefSelectValues(home, webauthnhome, typestr, id, pattern, count) {
	var url = home + '/query/' + encodeSafeURIComponent('typedef values') + '(typedef)?limit=none';
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
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){initTypedefSelectValues(home, webauthnhome, typestr, id, pattern, count)}, delay);
			}
		}
	});
}

function initTypedefTagrefs(home, webauthnhome, typestr, id, pattern, count) {
	var url = home + '/query/' + encodeSafeURIComponent('typedef tagref') + '(typedef;' + encodeSafeURIComponent('typedef tagref') + ')?limit=none';
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
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
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
		url = home + '/tags/typedef=' + encodeSafeURIComponent(typestr) + '(' + encodeSafeURIComponent('typedef values') + ')?limit=none';
	} else if (typedefTagrefs[typestr] != null) {
		url = home + '/query/' + encodeSafeURIComponent(typedefTagrefs[typestr]) + '(' + encodeSafeURIComponent(typedefTagrefs[typestr]) + ')' + encodeSafeURIComponent(typedefTagrefs[typestr]) + '?limit=none';
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
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
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
	if ($('#' + id).attr('clicked') != null) {
		return;
	} else {
		$('#' + id).attr('clicked', 'clicked');
	}
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
	var url = home + '/query/typedef(typedef;' + encodeSafeURIComponent('typedef description') + ')' + encodeSafeURIComponent('typedef description') + '?limit=none';
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
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
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
	if ($('#' + id).attr('clicked') != null) {
		return;
	} else {
		$('#' + id).attr('clicked', 'clicked');
	}
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
var FIELDSET_COUNTER;
var PAGE_PREVIEW;
var LAST_PAGE_PREVIEW;
var availableTags = null;
var availableTagdefs = null;
var allTagdefs = null;
var availableViews = null;
var ops = new Object();
var opsExcludeTypes = new Object();
var typedefSubjects = null;

var resultColumns = [];
var viewListTags = new Object();
var disableAjaxAlert = false;
var sortColumnsArray = new Array();
var editInProgress = false;
var tagInEdit = null;
var saveSearchConstraint;
var tagToMove = null;

var confirmQueryEditDialog = null;
var confirmAddTagDialog = null;
var confirmAddMultipleTagsDialog = null;

var queryFilter = new Object();

var dragAndDropBox;
var tipBox;

var movePageX;

var SELECT_LIMIT = 50;
var WINDOW_TAB = 0;
var PREVIEW_LIMIT;
var LAST_PREVIEW_LIMIT;
var select_tags = null;

var lastPreviewURL = null;
var lastEditTag = null;

var probe_tags;
var enabledDrag = true;
var userOp = new Object();
var localeTimezone;

var intervalPattern = new RegExp('\\((.+),(.+)\\)');

function queryHasFilters() {
	var ret = false;
	$.each(queryFilter, function(tag, value) {
		ret = true;
		return false;
	});
	return ret;
}

function clearFilter(tag) {
	delete queryFilter[tag];
	showPreview();
}

function clearAllFilters() {
	queryFilter = new Object();
	showPreview();
}

function hasTagValueOption(tag, val) {
	var ret = false;
	if (select_tags[tag] != null) {
		$.each(select_tags[tag], function(i, value) {
			var optionVal = htmlEscape(value);
			if (availableTags[tag] == 'timestamptz') {
				optionVal = getLocaleTimestamp(optionVal);
			}
			if (optionVal == val) {
				ret = true;
				return false;
			}
		});
	}
	return ret;
}

function appendTagValuesOptions(tag, id) {
	var select = $(document.getElementById(id));
	$.each(select_tags[tag], function(i, value) {
		var option = $('<option>');
		var optionVal = htmlEscape(value);
		if (availableTags[tag] == 'timestamptz') {
			optionVal = getLocaleTimestamp(optionVal);
		}
		option.text(optionVal);
		option.attr('value', optionVal);
		select.append(option);
	});
	if (select_tags[tag].length == 0) {
		alert("Warning: No values available for the operator.");
	}
}

function DisplayDragAndDropBox(e) {
	dragAndDropBox.css('left', String(parseInt(e.pageX) + 'px'));
	dragAndDropBox.css('top', String(parseInt(e.pageY) + 'px'));
	dragAndDropBox.html(tagToMove);
	dragAndDropBox.css('display', 'block');
	var header = $('#Query_Preview_header');
	var minX = parseInt(header.offset().left);
	var maxX = minX + header.width();
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
	var dx = tipBox.width() + 30;
	dx = (e.clientX >= $(window).width() * 2 / 3) ? -dx : 0;
	tipBox.css('left', String(parseInt(e.pageX + dx) + 'px'));
	tipBox.css('top', String(parseInt(e.pageY - 50) + 'px'));
	tipBox.css('display', 'block');
}

function HideTipBox() {
	tipBox.css('display', 'none');
}

function copyColumn(e, column) {
	e.preventDefault();
	if (!enabledDrag) {
		return;
	}
	tagToMove = column;
	movePageX = e.pageX;
}

function insertColumn(index1, index2, append) {
	var thead = $('#Query_Preview_header');
	for (var i=0; i < thead.children().length; i++) {
		var tr = getChild(thead, i+1);
		var col1 = getChild(tr, index1 + 2);
		var col2 = getChild(tr, index2 + 2);
		if (append) {
			col2.addClass('separator');
			col1.removeClass('separator');
			col1.insertAfter(col2);
		} else {
			if (index1 == (resultColumns.length - 1)) {
				col1.addClass('separator');
			}
			col1.insertBefore(col2);
			if (index1 == (resultColumns.length - 1)) {
				var col = getChild(tr, resultColumns.length+1);
				col.removeClass('separator');
			}
		}
	}
	var tbody = $('#Query_Preview_tbody');
	for (var i=0; i < tbody.children().length; i++) {
		var tr = getChild(tbody, i+1);
		if (tr.css('display') == 'none') {
			break;
		}
		var col1 = getChild(tr, index1 + 2);
		var col2 = getChild(tr, index2 + 2);
		if (append) {
			col2.addClass('separator');
			col1.removeClass('separator');
			col1.insertAfter(col2);
		} else {
			if (index1 == (resultColumns.length - 1)) {
				col1.addClass('separator');
			}
			col1.insertBefore(col2);
			if (index1 == (resultColumns.length - 1)) {
				var col = getChild(tr, resultColumns.length+1);
				col.removeClass('separator');
			}
		}
	}
}

function resetColumnsIndex() {
	var thead = $('#Query_Preview_header');
	var tr1 = getChild(thead, 1);
	var tr2 = getChild(thead, 2);
	var tr3 = getChild(thead, 3);
	for (var i=0; i < resultColumns.length; i++) {
		var td = getChild(tr1, (i+2));
		td.attr('iCol', '' + (i+1));
		td = getChild(tr2, (i+2));
		td.attr('iCol', '' + (i+1));
		td = getChild(tr3, (i+2));
		td.attr('iCol', '' + (i+1));
	}
	var tbody = $('#Query_Preview_tbody');
	for (var i=0; i < tbody.children().length; i++) {
		var tr = getChild(tbody, i+1);
		if (tr.css('display') == 'none') {
			break;
		}
		for (var j=0; j < resultColumns.length; j++) {
			var td = getChild(tr, j+2);
			td.attr('iCol', '' + (j+1));
		}
	}
}

function dropColumn(e, tag, append) {
	e.preventDefault();
	if (tagToMove == null) {
		return;
	}
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
	insertColumn(tagToMoveIndex, tagToDropIndex, append);
	resetColumnsIndex();
	$('td.highlighted').removeClass('highlighted');
	updatePreviewURL(true);
}

function updatePreviewURL(force) {
	var predUrl = getQueryPredUrl();
	var offset = '&offset=' + PAGE_PREVIEW * PREVIEW_LIMIT;
	var queryUrl = getQueryUrl(predUrl, '&limit=' + PREVIEW_LIMIT, encodeURIArray(resultColumns, ''), encodeURIArray(sortColumnsArray, ''), offset);
	$('#Query_URL').attr('href', queryUrl);
	if (force) {
		lastPreviewURL = queryUrl;
	}
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

function getChild(item, index) {
	return item.children(':nth-child(' + index + ')');
}

function getColumnOver(e) {
	var ret = new Object();
	var header = $('#Query_Preview_header');
	var minY = parseInt(header.offset().top);
	var minX = parseInt(header.offset().left);
	var maxY = minY + header.height();
	var maxX = minX + header.width();
	var x = parseInt(e.pageX);
	var y = parseInt(e.pageY);
	var tr = getChild(header, 2);
	minX += getChild(tr, 1).width();
	if (y < minY || y > maxY) {
		$('td.highlighted').removeClass('highlighted');
	} else if (x <= minX) {
		var children = tr.children();
		var tag = resultColumns[0];
		var th = $(children[1]).find('th');
		ret['tag'] = tag;
		ret['append'] = false;
		var trs = $('.tablerow');
		$('td.highlighted').removeClass('highlighted');
		$('td:nth-child(' + 2 + ')', trs).addClass('highlighted');
	} else if (x >= maxX) {
		var children = tr.children();
		var i = resultColumns.length;
		var tag = resultColumns[i-1];
		var th = $(children[i]).find('th');
		ret['tag'] = tag;
		ret['append'] = true;
	} else {
		var children = tr.children();
		for (var i=2; i <= resultColumns.length + 1; i++) {
			var left = (i <= resultColumns.length) ? parseInt($(children[i]).offset().left) : maxX;
			if (left >= x || i == resultColumns.length + 1) {
				var append = false;
				if (i == resultColumns.length + 1) {
					left = parseInt($(children[resultColumns.length]).offset().left);
					if (x >= (maxX + left)/2) {
						append = true;
					}
				}
				var tag = resultColumns[(i < resultColumns.length + 1) ? i-2 : resultColumns.length - 1];
				var th = $(children[i]).find('th');
				ret['tag'] = tag;
				ret['append'] = append;
				var trs = $('.tablerow');
				$('td.highlighted').removeClass('highlighted');
				if (!append) {
					$('td:nth-child(' +  i + ')', trs).addClass('highlighted');
				}
				break;
			}
		}
	}
	return ret;
}

function setNextPage() {
	PAGE_PREVIEW++;
	showPreview();
}

function setPreviousPage() {
	PAGE_PREVIEW--;
	showPreview();
}

function initPreview() {
	var searchString = window.location.search;
	if (searchString != null && searchString.length > 1) {
		searchString = searchString.substring(1);
		var searchOptions = searchString.split('&');
		var offset = 0;
		$.each(searchOptions, function(i, option) {
			var value = option.split('=');
			if (value[0] == 'limit') {
				PREVIEW_LIMIT = parseInt(value[1]);
				LAST_PREVIEW_LIMIT = PREVIEW_LIMIT;
				$('#previewLimit').val(value[1]);
			} else if (value[0] == 'offset') {
				offset = parseInt(value[1]);
			}
		});
		PAGE_PREVIEW = offset / PREVIEW_LIMIT;
		LAST_PAGE_PREVIEW = PAGE_PREVIEW;
	}
}

function initPSOC(home, user, webauthnhome, basepath, querypath) {
	HOME = home;
	USER = user;
	WEBAUTHNHOME = webauthnhome;
	ROW_COUNTER = 0;
	VAL_COUNTER = 0;
	ROW_TAGS_COUNTER = 0;
	ROW_SORTED_COUNTER = 0;
	PREVIEW_COUNTER = 0;
	ENABLE_ROW_HIGHLIGHT = true;
	FIELDSET_COUNTER = 0;
	PAGE_PREVIEW = 0;
	LAST_PAGE_PREVIEW = 0;
	PREVIEW_LIMIT = parseInt($('#previewLimit').val());
	LAST_PREVIEW_LIMIT = PREVIEW_LIMIT;
	
	initPreview();
	// build the userOp dictionary
	$.each(ops, function(key, value) {
		userOp[value] = key;
	});
	$('#pagePrevious').attr('src', home + '/static/back_disabled.jpg');
	$('#pageNext').attr('src', home + '/static/forward_disabled.jpg');
	loadTypedefs();
	$(document).mousemove(function(e){
		e.preventDefault();
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
			dropColumn(e, ret['tag'], ret['append']);
		}
	});
	loadTags();
	if (querypath != null) {
		var querypathJSON = $.parseJSON( querypath );
		var lpreds = querypathJSON[0]['lpreds'];
		$.each(lpreds, function(i, pred) {
			resultColumns.push(pred['tag']);
		});
		var spreds = querypathJSON[0]['spreds'];
		$.each(spreds, function(i, item) {
			var tag = item['tag'];
			if (queryFilter[tag] == null) {
				queryFilter[tag] = new Array();
			}
			if (availableTags[tag] == 'timestamptz' || 
				availableTags[tag] == 'date' ||
				availableTags[tag] == 'int8' ||
				availableTags[tag] == 'float8') {
				var m = intervalPattern.exec(item['vals'][0]);
				if (m != null && m.length > 2) {
					var val1 = m[1];
					var val2 = m[2];
					if (availableTags[tag] == 'timestamptz') {
						val1 = getLocaleTimestamp(val1);
						val2 = getLocaleTimestamp(val2);
					}
					item['vals'] = new Array();
					item['vals'].push(val1);
					item['vals'].push(val2);
					item['op'] = 'Between';
					item['opUser'] = 'Between';
				}
			}
			var pred = new Object();
			pred['op'] = item['op'];
			pred['vals'] = item['vals'];
			if (pred['op'] == null) {
				pred['opUser'] = 'Tagged';
			} else if (pred['op'] == 'Between') {
				pred['opUser'] = item['opUser'];
			} else {
				pred['opUser'] = userOp[pred['op']];
			}
			queryFilter[item['tag']].push(pred);
		});
		var otags = querypathJSON[0]['otags'];
		$.each(otags, function(i, item) {
			sortColumnsArray.push(item);
		});
	} else {
		setViewTags('default');
		$.each(viewListTags['default'], function(i, tag) {
			resultColumns.unshift(tag);
		});
	}
	
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
		height: ($(window).height() < 250 ? $(window).height() : 250),
		modal: false,
		resizable: true,
		width: ($(window).width() < 450 ? $(window).width() : 450),
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
		height: ($(window).height() < 250 ? $(window).height() : 250),
		modal: false,
		resizable: true,
		width: ($(window).width() < 450 ? $(window).width() : 450),
	});
	dragAndDropBox = $('#DragAndDropBox');
	tipBox = $('#TipBox');
	
	// set the locale timezone
	var now = new Date();
	localeTimezone = now.getTimezoneOffset();
	var tzsign = localeTimezone > 0 ? '-' : '+';
	localeTimezone = Math.abs(localeTimezone);
	var tzmin = localeTimezone % 60;
	localeTimezone = tzsign + ('0' + (localeTimezone - tzmin) / 60).slice(-2) + ':' + ('0' + tzmin).slice(-2);
	showPreview();
}

function loadTypedefs() {
	var url = HOME + '/query/typedef(typedef;' + encodeSafeURIComponent('typedef values') + ';' +encodeSafeURIComponent('typedef dbtype') + ';' +encodeSafeURIComponent('typedef tagref') + ')?limit=none';
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
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

function loadTags() {
	var url = HOME + '/query/tagdef(tagdef;' + 
				encodeSafeURIComponent('tagdef type') + ';' + 
				encodeSafeURIComponent('tagdef multivalue') + ';' +
				encodeSafeURIComponent('tagdef unique') + ')?limit=none';
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
			var results = ['bytes', 'vname', 'url', 'template%20mode', 'id'];
			$.each(data, function(i, object) {
				availableTagdefs.push(object['tagdef']);
				availableTags[object['tagdef']] = object['tagdef type'];
				allTagdefs[object['tagdef']] = object;
				if (object['tagdef unique']) {
					var encodeValue = encodeSafeURIComponent(object['tagdef']);
					if (!results.contains(encodeValue)) {
						results.push(encodeValue);
					}
					unique_tags.push(object['tagdef']);
				}
			});
			availableTagdefs.sort(compareIgnoreCase);
			probe_tags = results.join(';');
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

function loadAvailableTags(id) {
	if ($('#' + id).attr('clicked') != null) {
		return;
	} else {
		$('#' + id).attr('clicked', 'clicked');
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
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

function loadAvailableViews(id) {
	if ($('#' + id).attr('clicked') != null) {
		return;
	} else {
		$('#' + id).attr('clicked', 'clicked');
	}
	loadViews();
	var select = $('#' + id);
	$.each(availableViews, function(i, object) {
		var option = $('<option>');
		option.text(object);
		option.attr('value', object);
		select.append(option);
	});
}

function setViewTags(tag) {
	if (viewListTags[tag] != null) {
		return;
	}
	var url = HOME + '/query/view=' + encodeSafeURIComponent(tag) + '(' + encodeSafeURIComponent('_cfg_file list tags') + ')' + encodeSafeURIComponent('_cfg_file list tags');
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
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

function addToQueryTable(tableId, tag) {
	var tbody = getChild($('#' + tableId), 2);
	var id = makeId('row', ++ROW_COUNTER);
	var tr = $('<tr>');
	tr.attr('id', id);
	tbody.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.attr('valign', 'top');
	var select = getSelectTagOperator(tag, availableTags[tag]);
	var selId = select.attr('id');
	td.append(select);
	td = $('<td>');
	tr.append(td);
	if (availableTags[tag] != 'empty') {
		var table = $('<table>');
		table.attr('id', makeId('table', ROW_COUNTER));
		td.append(table);
		var tdTable = $('<td>');
		tdTable.css('text-align', 'center');
		tdTable.css('margin-top', '0px');
		tdTable.css('margin-bottom', '0px');
		tdTable.css('padding', '0px');
		tr.append(tdTable);
		addNewValue(ROW_COUNTER, availableTags[tag], selId, tag, null);
		if ($('#' + selId).val() == 'Between') {
			tdTable.css('display', 'none');
		} else if ($('#' + selId).val() == 'Tag absent') {
			td.css('display', 'none');
			var thead = getChild($('#' + tableId), 1);
			var tr = getChild(thead, 1);
			var th = getChild(tr, 2);
			th.css('display', 'none');
		}
	} else {
		var thead = getChild($('#' + tableId), 1);
		var tr = getChild(thead, 1);
		var th = getChild(tr, 2);
		th.css('display', 'none');
	}
}

function deleteRow(id) {
	var row = $('#' + id);
	var tableId = row.parent().parent().attr('id');
	row.remove();
	showPreview();
}

function deleteConstraintRow(rowId, tableId, tagId) {
	var children = $('#' + makeId('queryDiv', tagId)).children();
	if (children.length > 1) {
		$('#' + tableId).remove();
	} else {
		var row = $('#' + rowId);
		getChild(row, 3).remove();
		getChild(row, 1).remove();
		$('#' + tableId).addClass('orphan');
	}
	showPreview();
}

function deleteValue(id, tableId) {
	var tr = $('#' + id);
	var table = $('#' + tableId);
	var tbody = getChild(table, 1);
	if (tbody.children().length == 1) {
		var td = getChild(tr, 1);
		var input = getChild(td, 1);
		input.val('');
	} else {
		$('#' + id).remove();
	}
	showPreview();
}

function getSelectTagOperator(tag, type) {
	var select = $('<select>');
	var id = makeId('select', ROW_COUNTER);
	select.attr({	id: id,
					name: id });
	select.change({	row: ROW_COUNTER,
					selId: id,
					tag: tag },
					function(event) {displayValuesTable(event.data.row, event.data.selId, event.data.tag);});
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
	if (select_tags[tag] != null && select_tags[tag].length == 0) {
		select.val('Tag absent');
		select.attr('prevVal', 'Tag absent');
	} else if (type == 'timestamptz' || type == 'date') {
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

function addNewValue(row, type, selectOperatorId, tag, values) {
	var selVal = $('#' + selectOperatorId).val();
	var valId = makeId('vals', ++VAL_COUNTER);
	var table = $('#' + makeId('table', row));
	table.parent().css('display', '');
	var tr = $('<tr>');
	tr.attr('id', valId);
	table.append(tr);
	if (selVal == 'Between') {
		if (!isSelect(tag, type)) {
			var td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			var input = $('<input>');
			if (availableTags[tag] == 'timestamptz') {
				input.addClass('datetimepicker');
			} else if (availableTags[tag] == 'date') {
				input.addClass('datepicker');
			}
			input.attr('type', 'text');
			input.mouseout(function(event) {showPreview();});
			input.change(function(event) {showPreview();});
			td.append(input);
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			td.append('AND');
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			input = $('<input>');
			if (availableTags[tag] == 'timestamptz') {
				input.addClass('datetimepicker');
			} else if (availableTags[tag] == 'date') {
				input.addClass('datepicker');
			}
			input.attr('type', 'text');
			input.mouseout(function(event) {showPreview();});
			input.change(function(event) {showPreview();});
			td.append(input);
		} else {
			var td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			if (values != null && !hasTagValueOption(tag, values[0])) {
				var input = $('<input>');
				if (availableTags[tag] == 'timestamptz') {
					input.addClass('datetimepicker');
				} else if (availableTags[tag] == 'date') {
					input.addClass('datepicker');
				}
				input.attr('type', 'text');
				input.mouseout(function(event) {showPreview();});
				input.change(function(event) {showPreview();});
				td.append(input);
			} else {
				var select = $('<select>');
				var selid = makeId('select', 'value', VAL_COUNTER);
				select.attr('id', selid);
				select.change(function(event) {showPreview();});
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
			td = $('<td>');
			tr.append(td);
			td.append('AND');
			td = $('<td>');
			tr.append(td);
			if (values != null && !hasTagValueOption(tag, values[1])) {
				var input = $('<input>');
				if (availableTags[tag] == 'timestamptz') {
					input.addClass('datetimepicker');
				} else if (availableTags[tag] == 'date') {
					input.addClass('datepicker');
				}
				input.attr('type', 'text');
				input.mouseout(function(event) {showPreview();});
				input.change(function(event) {showPreview();});
				td.append(input);
			} else {
				var select = $('<select>');
				var selid = makeId('select', 'value', ++VAL_COUNTER);
				select.attr('id', selid);
				select.change(function(event) {showPreview();});
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
	} else if (!isSelect(tag, type) || (selVal != 'Equal' && selVal != 'Not equal')) {
		td = $('<td>');
		tr.append(td);
		td.css('border-width', '0px');
		var input = $('<input>');
		if (availableTags[tag] == 'timestamptz') {
			input.addClass('datetimepicker');
		} else if (availableTags[tag] == 'date') {
			input.addClass('datepicker');
		}
		input.attr('type', 'text');
		input.mouseout(function(event) {showPreview();});
		input.change(function(event) {showPreview();});
		td.append(input);
	} else {
		var td = $('<td>');
		tr.append(td);
		td.css('border-width', '0px');
		if (values != null && !hasTagValueOption(tag, values[0])) {
			var input = $('<input>');
			if (availableTags[tag] == 'timestamptz') {
				input.addClass('datetimepicker');
			} else if (availableTags[tag] == 'date') {
				input.addClass('datepicker');
			}
			input.attr('type', 'text');
			input.mouseout(function(event) {showPreview();});
			input.change(function(event) {showPreview();});
			td.append(input);
		} else {
			var select = $('<select>');
			var selid = makeId('select', 'value', VAL_COUNTER);
			select.attr('id', selid);
			select.change(function(event) {showPreview();});
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
	if (selVal != 'Between') {
		td = $('<td>');
		tr.append(td);
		var imgPlus = $('<img>');
		imgPlus.attr({	src: HOME + '/static/plus.png',
					    width: '16',
					    height: '16',
						alt: '+' });
		imgPlus.click({	row: ROW_COUNTER,
						type: availableTags[tag],
						selectOperatorId: selectOperatorId,
						tag: tag,
						values: null },
						function(event) {addNewValue(event.data.row, event.data.type, event.data.selectOperatorId, event.data.tag, event.data.values);});
		td.append(imgPlus);
		td = $('<td>');
		tr.append(td);
		var img = $('<img>');
		img.attr({	src: HOME + '/static/minus.png',
				    width: '16',
				    height: '16',
					alt: '-' });
		img.click({ id: valId,
					tableId: makeId('table', row) },
					function(event) {deleteValue(event.data.id, event.data.tableId);});
		td.append(img);
	}
	var now = new Date();
	$('.datetimepicker').datetimepicker({	dateFormat: 'yy-mm-dd',
											timeFormat: 'hh:mm:ss.l',
											hour: now.getHours(),
											minute: now.getMinutes(),
											second: now.getSeconds(),
											millisec: now.getMilliseconds(),
											showSecond: true,
											showMillisec: true,
											changeYear: true,
											millisecText: 'Millisec'
	});
	$('.datepicker').datetimepicker({	dateFormat: 'yy-mm-dd',
										timeFormat: '',
										separator: '',
										changeYear: true,
										showTime: false,
										showHour: false,
										showMinute: false
	});
}

function getQueryTags(tableId) {
	var ret = new Array();
	var tbody = getChild($('#' + tableId), 1);
	$.each(tbody.children(), function(i, tr) {
		ret.push(encodeSafeURIComponent(getChild($(tr), 2).html()));
	});
	if (ret.length == 0) {
		ret = '';
	}
	
	return ret;
}

function encodeURIArray(values, suffix) {
	var ret = new Array();
	for (var i=0; i < values.length; i++) {
		ret.push(encodeSafeURIComponent(values[i] + suffix));
	}
	return ret;
}

function getQueryPredUrl() {
	if (tagInEdit != null && editInProgress) {
		var tagConstraintDiv = $('#' +makeId('queryDiv', tagInEdit.split(' ').join('_')));
		saveTagPredicate(tagInEdit, tagConstraintDiv);
	}
	var query = new Array();
	var url = '';
	$.each(queryFilter, function(tag, preds) {
		if (tag == tagInEdit && !editInProgress) {
			return true;
		}
		var suffix = '';
		if (availableTags[tag] == 'timestamptz') {
			suffix = localeTimezone;
		}
		$.each(preds, function(i, pred) {
			if (pred['opUser'] == 'Between') {
				query.push(encodeSafeURIComponent(tag) + '=' + encodeSafeURIComponent('(' + pred['vals'][0] + suffix + ',' +
																pred['vals'][1] + suffix + ')'));
			} else if (pred['opUser'] != 'Tagged' && pred['opUser'] != 'Tag absent') {
				query.push(encodeSafeURIComponent(tag) + pred['op'] + encodeURIArray(pred['vals'], suffix).join(','));
			} else {
				query.push(encodeSafeURIComponent(tag) + (pred['op'] != null ? pred['op'] : ''));
			}
		});
	});
	if (query.length > 0) {
		url = query.join(';');
	}
	url = HOME + '/query/' + url;
	return url;
}

function getQueryUrl(predUrl, limit, encodedResultColumns, encodedSortedColumns, offset) {
	var retTags = '(' + encodedResultColumns.join(';') + ')';
	var encodedResultColumns = new Array();
	var sortTags = encodedSortedColumns.join(',');
	var latest = '?versions=' + $('#versions').val();
	var url = predUrl + retTags + sortTags + latest + limit + offset;
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
		var table = $('#' + selId).parent().parent().parent().parent();
		var thead = getChild(table, 1);
		var tr = getChild(thead, 1);
		var th = getChild(tr, 2);
		th.css('display', 'none');
	} else {
			var table = $('#' + selId).parent().parent().parent().parent();
			var thead = getChild(table, 1);
			var tr = getChild(thead, 1);
			var th = getChild(tr, 2);
			th.css('display', '');
			if (clearValuesTable) {
				addNewValue(row, availableTags[tag], selId, tag, null);
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
	var offset = '';
	if (!editInProgress) {
		offset = '&offset=' + PAGE_PREVIEW * PREVIEW_LIMIT;
	}
	var predUrl = getQueryPredUrl();
	var queryUrl = getQueryUrl(predUrl, limit, encodeURIArray(resultColumns, ''), encodeURIArray(sortColumnsArray, ''), offset);
	if (lastPreviewURL == queryUrl && lastEditTag == tagInEdit && PREVIEW_LIMIT == LAST_PREVIEW_LIMIT) {
		return;
	}
	document.body.style.cursor = "wait";
	lastPreviewURL = queryUrl;
	lastEditTag = tagInEdit;
	updatePreviewURL(false);
	showQueryResultsPreview(predUrl, limit, offset);
}

function showQueryResultsPreview(predUrl, limit, offset) {
	var columnArray = new Array();
	columnArray.push('id');
	var queryUrl = getQueryUrl(predUrl, '&range=count', encodeURIArray(columnArray, ''), new Array(), '');
	$.ajax({
		url: queryUrl,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
		success: function(data, textStatus, jqXHR) {
			var totalRows = data[0]['id'];
			showQueryResultsTable(predUrl, limit, totalRows, offset);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (!disableAjaxAlert) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, queryUrl);
			}
		}
	});
}

function initDropDownList(tag) {
	var predUrl = getQueryPredUrl();
	var totalRows = 0;
	var columnArray = new Array();
	columnArray.push(tag);
	queryUrl = getQueryUrl(predUrl, '&range=count', encodeURIArray(columnArray, ''), new Array(), '');
	select_tags = new Object();
	$.ajax({
		url: queryUrl,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		accepts: {text: 'application/json'},
		dataType: 'json',
		success: function(data, textStatus, jqXHR) {
			totalRows = data[0][tag];
			if (totalRows == 0) {
				select_tags[tag] = new Array();
			} else if (totalRows > 0 && totalRows <= SELECT_LIMIT) {
				queryUrl = getQueryUrl(predUrl, '&range=values', encodeURIArray(columnArray, ''), new Array(), '');
				$.ajax({
					url: queryUrl,
					headers: {'User-agent': 'Tagfiler/1.0'},
					async: false,
					accepts: {text: 'application/json'},
					dataType: 'json',
					success: function(data, textStatus, jqXHR) {
						select_tags[tag] = data[0][tag];
					},
					error: function(jqXHR, textStatus, errorThrown) {
						if (!disableAjaxAlert) {
							handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, queryUrl);
						}
					}
				});
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (!disableAjaxAlert) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, queryUrl);
			}
		}
	});
}

function updatePreviewLimit() {
	LAST_PREVIEW_LIMIT = PREVIEW_LIMIT;
	PREVIEW_LIMIT = parseInt($('#previewLimit').val());
	// update the page counter
	PAGE_PREVIEW = Math.floor((LAST_PREVIEW_LIMIT * PAGE_PREVIEW / PREVIEW_LIMIT));
	showPreview();
}

function showColumnDetails(column, count) {
	var id = makeId('arrow_up', column.split(' ').join('_'), count);
	$('#' + id).css('display', '');
	id = makeId('delete', column.split(' ').join('_'), count);
	$('#' + id).css('display', '');
}

function hideColumnDetails(column, count) {
	var id = makeId('arrow_up', column.split(' ').join('_'), count);
	$('#' + id).css('display', 'none');
	id = makeId('delete', column.split(' ').join('_'), count);
	$('#' + id).css('display', 'none');
}

function showQueryResultsTable(predUrl, limit, totalRows, offset) {
	var previewRows = 0;
	var predList = new Array();
	predList = predList.concat(resultColumns);
	if (!resultColumns.contains('id')) {
		predList = predList.concat('id');
	}
	var queryUrl = getQueryUrl(predUrl, limit == '' ? '&limit=' + (PREVIEW_LIMIT != -1 ? PREVIEW_LIMIT : 'none') : limit, encodeURIArray(predList, ''), encodeURIArray(sortColumnsArray, ''), offset);
	var queryPreview = $('#Query_Preview');
	var table = getChild(queryPreview, 1);
	if (table.get(0) == null) {
		table = $('<table>');
		table.addClass('display');
		table.attr({	border: '0',
						cellpadding: '0',
						cellspacing: '0' });
		queryPreview.append(table);
		var thead = $('<thead>');
		thead.css('background-color', '#F2F2F2');
		table.append(thead);
		thead.attr('id', 'Query_Preview_header');
		var tr = $('<tr>');
		thead.append(tr);
		tr = $('<tr>');
		thead.append(tr);
		tr = $('<tr>');
		thead.append(tr);
		var tbody = $('<tbody>');
		tbody.attr('id', 'Query_Preview_tbody');
		table.append(tbody);
		var tfoot = $('<tfoot>');
		tfoot.attr('id', 'Query_Preview_tfoot');
		table.append(tfoot);
		tr = $('<tr>');
		tr.addClass('headborder');
		tfoot.append(tr);
	}

	// build the table header
	var thead = getChild(table, 1);
	var tfoot = getChild(table, 3);
	var tr1 = getChild(thead, 1);
	var tr2 = getChild(thead, 2);
	var tr3 = getChild(thead, 3);
	var trfoot = getChild(tfoot, 1);
	if (getChild(tr1, 1).get(0) == null) {
		// first column for context menu
		var td = $('<td>');
		td.attr('width', '1%');
		td.css('background-color', 'white');
		tr1.append(td);
		td = $('<td>');
		td.attr('width', '1%');
		td.css('background-color', 'white');
		tr2.append(td);
		td = $('<td>');
		td.attr('width', '1%');
		td.css('background-color', 'white');
		tr3.append(td);
	}
	var columnLimit = 1;
	$.each(resultColumns, function(i, column) {
		columnLimit = i + 2;
		var tagId = column.split(' ').join('_');
		var thId = makeId(tagId, 'th', PREVIEW_COUNTER);
		var td = getChild(tr1, i+2);
		if (td.get(0) == null) {
			var td = $('<td>');
			tr1.append(td);
			td.addClass('separator');
			td.addClass('tableheadercell');
			td.addClass('topnav');
			td.css('text-align', 'center');
			
			var th = $('<th>');
			th.addClass('separator');
			th.addClass('tableheadercell');
			tr2.append(th);
			
			td = $('<td>');
			td.addClass('tableheadercell');
			td.addClass('separator');
			tr3.append(td);
			var divConstraint = $('<div>');
			td.append(divConstraint);
			
			th = $('<th>');
			trfoot.append(th);
			th.html('&nbsp;');
		}
		var td = getChild(tr1, i+2);
		if (i < (resultColumns.length - 1)) {
			if (!td.hasClass('separator')) {
				td.addClass('separator');
				td = getChild(tr2, i+2);
				td.addClass('separator');
				td = getChild(tr3, i+2);
				td.addClass('separator');
			}
		} else {
			if (td.hasClass('separator')) {
				td.removeClass('separator');
				td = getChild(tr2, i+2);
				td.removeClass('separator');
				td = getChild(tr3, i+2);
				td.removeClass('separator');
			}
		}
		var columSortId = makeId('sort', column.split(' ').join('_'), PREVIEW_COUNTER);
		var tdSort = getChild(tr1, i+2);
		tdSort.css('display', '');
		tdSort.html('');
		tdSort.attr('id', columSortId);
		tdSort.attr('iCol', '' + (i+1));
		var sortValue = getSortOrder(column);
		var label = $('<label>');
		tdSort.append(label);
		if (sortValue != '') {
			label.html(sortValue);
			var content;
			switch(parseInt(sortValue)) {
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
			label.hover( function(e) {
				DisplayTipBox(e, content);
			}, function() {
				HideTipBox();
			});
		} else {
			label.html('&nbsp;');
		}
		var ul = $('<ul>');
		ul.addClass('subnav');
		tdSort.append(ul);
		var li = $('<li>');
		li.addClass('item');
		li.html('Clear column filter');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {clearFilter(column);});
		ul.append(li);
		if (queryFilter[column] == null) {
			li.css('display', 'none');
		}
		li = $('<li>');
		li.addClass('item');
		li.html('Edit column filter');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {event.preventDefault(); editQuery(column);});
		ul.append(li);
		li = $('<li>');
		li.addClass('item');
		li.html('Delete column');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {deleteColumn(column, PREVIEW_COUNTER);});
		ul.append(li);
		li = $('<li>');
		li.addClass('item');
		li.html((sortValue == '' ? 'Sort' : 'Unsort') + ' column');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {sortColumn(column, columSortId, PREVIEW_COUNTER, (sortValue == ''), true);});
		ul.append(li);
		var span = $('<span>');
		tdSort.append(span);
		
		var th = getChild(tr2, i+2);
		th.css('display', '');
		th.html('');
		th.attr('iCol', '' + (i+1));
		th.unbind('mousedown mouseup');
		th.mousedown(function(event) {copyColumn(event, column);});
		th.mouseup(function(event) {dropColumn(event, column, false);});
		th.attr('id', thId);
		th.append(column);
		
		var td3 = getChild(tr3, i+2);
		td3.css('display', '');
		td3.attr('iCol', '' + (i+1));
		var divConstraint = getChild(td3, 1);
		divConstraint.css('white-space', 'nowrap');
		divConstraint.attr('id', makeId('constraint', column.split(' ').join('_'), PREVIEW_COUNTER));
		divConstraint.html('');
		if (queryFilter[column] != null) {
			var constraint = getTagSearchDisplay(column);
			divConstraint.append(constraint);
		}
		
		var tdfoot = getChild(trfoot, i+2);
		tdfoot.css('display', '');
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
						tr.addClass('headborder');
					}
				}
				tr.css('display', '');
				odd = !odd;
				if (getChild(tr, 1).get(0) == null) {
					// context menu here
					var td = $('<td>');
					td.attr('width', '1%');
					td.addClass('separator');
					td.attr('valign', 'top');
					tr.append(td);
				}
				var td = getChild(tr, 1);
				td.html('');
				getIdContextMenuSlot(td, row['id']);
				$.each(resultColumns, function(j, column) {
					var td = getChild(tr, j+2);
					if (td.get(0) == null) {
						td = $('<td>');
						td.addClass('tablecell');
						td.addClass('separator');
						td.attr('valign', 'top');
						tr.append(td);
					}
					td.css('display', '');
					td.removeClass();
					td.addClass(column.replace(/ /g, ''));
					td.addClass('tablecell');
					if (j < (resultColumns.length - 1)) {
						td.addClass('separator');
					}
					td.attr('iCol', '' + (j+1));
					td.html('');
					if (row[column] != null) {
						if (!allTagdefs[column]['tagdef multivalue']) {
							if (row[column] === true) {
								td.html('is set');
							} else if (row[column] === false) {
								td.html('not set');
							} else {
								if (column == 'name') {
									td.html(htmlEscape(row[column]));
								} else if (column == 'url') {
									var a = $('<a>');
									td.append(a);
									a.attr('href', row[column]);
									a.html(row[column]);
								} else {
									var cellVal = htmlEscape(row[column]);
									if (availableTags[column] == 'timestamptz') {
										cellVal = getLocaleTimestamp(cellVal);
									}
									td.html(cellVal);
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
				var minRow = 1;
				if (offset != '') {
					offset = parseInt(offset.split('=')[1]);
					minRow = offset + 1;
				}
				var maxRow = minRow + PREVIEW_LIMIT - 1;
				b.append('Showing ' + minRow + ' to ' + maxRow + ' of ' + totalRows + ' results.');
				if (minRow > PREVIEW_LIMIT) {
					$('#pagePrevious').attr('src', HOME + '/static/back.jpg');
					$('#pagePrevious').unbind('click');
					$('#pagePrevious').click(function(event){setPreviousPage();});
				} else {
					$('#pagePrevious').attr('src', HOME + '/static/back_disabled.jpg');
					$('#pagePrevious').unbind('click');
				}
				if (maxRow < totalRows) {
					$('#pageNext').attr('src', HOME + '/static/forward.jpg');
					$('#pageNext').unbind('click');
					$('#pageNext').click(function(event){setNextPage();});
				} else {
					$('#pageNext').attr('src', HOME + '/static/forward_disabled.jpg');
					$('#pageNext').unbind('click');
				}
			} else {
				$('#pagePrevious').attr('src', HOME + '/static/back_disabled.jpg');
				$('#pageNext').attr('src', HOME + '/static/forward_disabled.jpg');
				$('#pagePrevious').unbind('click');
				$('#pageNext').unbind('click');
				b.html('Showing all ' + previewRows + ' results.');
			}
			var tableLength = tbody.children().length;
			for (var i=rowLimit; i < tableLength; i++) {
				var tr = getChild(tbody, i+1);
				if (tr.css('display') == 'none') {
					break;
				}
				if (i < PREVIEW_LIMIT) {
					tr.css('display', 'none');
				} else {
					tr.remove();
					tableLength--;
					i--;
				}
			}
			$('td.topnav ul.subnav li.item').click(function(event) {event.preventDefault();});
			$('td.topnav ul.subnav li.item').mouseup(function(event) {event.preventDefault();});
			$('td.topnav span').click(function() {
				enabledDrag = false;
				var ul = $(this).parent().find("ul.subnav");
				if (ul.children().length == 0) {
					fillIdContextMenu(ul);
				}
				var height = $(this).height();
				var top = ($(this).position().top + height) + 'px';
				$('ul.subnav').css('top', top);
				var left = $(this).position().left + $(this).width() - 170;
				if (left < 0) {
					left = 0;
				}
				left += 'px';
				$('ul.subnav').css('left', left);
				
				//Following events are applied to the subnav itself (moving subnav up and down)
				$(this).parent().find("ul.subnav").slideDown('fast').show(); //Drop down the subnav on click
		
				$(this).parent().hover(function() {
				}, function(){	
					$(this).parent().find("ul.subnav").slideUp('slow'); //When the mouse hovers out of the subnav, move it back up
					enabledDrag = true;
				});
		
				//Following events are applied to the trigger (Hover events for the trigger)
				}).hover(function() { 
					$(this).addClass("subhover"); //On hover over, add class "subhover"
				}, function(){	//On Hover Out
					$(this).removeClass("subhover"); //On hover out, remove class "subhover"
			});
			$('.tablecell').hover( function() {
				var iCol = parseInt($(this).attr('iCol'));
				var trs = $('.tablerow');
				$('td:nth-child('+(iCol+1)+')', trs).addClass('highlighted');
			}, function() {
				$('td.highlighted').removeClass('highlighted');
			});
			$('.tableheadercell').hover( function(e) {
				var iCol = parseInt($(this).attr('iCol'));
				var trs = $('.tablerow');
				$('td:nth-child('+(iCol+1)+')', trs).addClass('highlighted');
			}, function() {
				if (tagToMove == null) {
					$('td.highlighted').removeClass('highlighted');
				}
			});
			$('#clearAllFilters').css('display', queryHasFilters() ? '' : 'none');
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (!disableAjaxAlert) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, queryUrl);
			}
		}
	});
	document.body.style.cursor = "default";
}

function fillIdContextMenu(ul) {
	var id = ul.attr('idVal')
	var subject = null;
	var idUrl = HOME + '/query/id=' + id + '(' + probe_tags + ')';
	$.ajax({
		url: idUrl,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(iddata, textStatus, jqXHR) {
			subject = iddata[0];
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, idUrl);
		}
	});
	var results = subject2identifiers(subject);
	var dtype = results['dtype'];
	if (dtype == 'template') {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({	target: '_newtab2' + ++WINDOW_TAB,
					href: HOME + '/file/' + results['datapred'] });
		a.html('View ' + results['dataname']);
	} else if (dtype == 'url') {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({	target: '_newtab2' + ++WINDOW_TAB,
					href: subject['url'] });
		a.html('View ' + results['dataname']);
	} else if (dtype == 'file') {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({	target: '_newtab2' + ++WINDOW_TAB,
					href: HOME + '/file/' + results['datapred'] });
		a.html('Download ' + results['dataname']);
	}
	var li = $('<li>');
	ul.append(li);
	var a = $('<a>');
	li.append(a);
	a.attr({	target: '_newtab2' + ++WINDOW_TAB,
				href: HOME + '/tags/' + results['datapred'] });
	a.html('View tags page');
}

function getIdContextMenuSlot(td, id) {
	td.addClass('topnav');
	var ul = $('<ul>');
	ul.attr('idVal', '' + id);
	td.append(ul);
	ul.addClass('subnav');
	var span = $('<span>');
	td.append(span);
}

function htmlEscape(str) {
    return String(str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
}

function sortColumn(column, id, count, sort) {
	if (sort) {
		sortColumnsArray.push(column);
		var length = sortColumnsArray.length;
		getChild($('#' + id), 1).html('' + length);
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
		getChild($('#' + id), 1).hover( function(e) {
			DisplayTipBox(e, content);
		}, function() {
			HideTipBox();
		});
	} else {
		stopSortColumn(column, count);
		getChild($('#' + id), 1).unbind('mouseenter mouseleave');
	}
	showPreview();
}

function stopSortColumn(tag, count) {
	var id = makeId('sort', tag.split(' ').join('_'), count);
	getChild($('#' + id), 1).html('&nbsp;');
	var index = -1;
	$.each(sortColumnsArray, function(i, column) {
		if (column == tag) {
			index = i;
			return false;
		}
	});
	sortColumnsArray.splice(index, 1);
	$.each(sortColumnsArray, function(i, column) {
		if (i < index) {
			return true;
		}
		var sortId = makeId('sort', column.split(' ').join('_'), count);
		var val = parseInt(getChild($('#' + sortId), 1).html()) - 1;
		getChild($('#' + sortId), 1).html('' + val);
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
			getChild($('#' + id), 1).hover( function(e) {
				DisplayTipBox(e, content);
			}, function() {
				HideTipBox();
			});
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
		var col = getChild(tr, index + 2);
		col.css('display', 'none');
	}
	var tbody = $('#Query_Preview_tbody');
	for (var i=0; i < tbody.children().length; i++) {
		var tr = getChild(tbody, i+1);
		if (tr.css('display') == 'none') {
			break;
		}
		var col = getChild(tr, index + 2);
		col.css('display', 'none');
	}
	var tfoot = $('#Query_Preview_tfoot');
	var tr = getChild(tfoot, 1);
	var col = getChild(tr, index + 2);
	col.css('display', 'none');
}

function deleteColumn(column, count) {
	$.each(sortColumnsArray, function(i, tag) {
		if (tag == column) {
			stopSortColumn(column, count);
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
		insertColumn(i+1, i, false);
	}
	resetColumnsIndex();
	hideColumn(resultColumns.length - 1);
	resultColumns.splice(deleteIndex, 1);
	updatePreviewURL(true);
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
	tagInEdit = tag;
	initDropDownList(tag);
	editInProgress = true;
	LAST_PAGE_PREVIEW = PAGE_PREVIEW;
	PAGE_PREVIEW = 0;
	//disableAjaxAlert = true;
	saveSearchConstraint = queryFilter[tag];
	addFilterToQueryTable(tag);
}

function cancelEdit(tag) {
	if (!editInProgress) {
		confirmQueryEditDialog.remove();
		confirmQueryEditDialog = null;
		tagInEdit = null;
		select_tags = null;
		return true;
	}
	
	confirmQueryEditDialog.remove();
	confirmQueryEditDialog = null;
	delete queryFilter[tag];
	if (saveSearchConstraint != null) {
		queryFilter[tag] = saveSearchConstraint;
	}
	PAGE_PREVIEW = LAST_PAGE_PREVIEW;
	//disableAjaxAlert = false;
	editInProgress = false;
	tagInEdit = null;
	select_tags = null;
	$('#queryDiv').html('');
	$('#queryDiv').css('display', 'none');
	showPreview();
	return true;
}

function saveTagQuery(tag) {
	var tagConstraintDiv = $('#' +makeId('queryDiv', tag.split(' ').join('_')));
	saveTagPredicate(tag, tagConstraintDiv);
	var tagId = makeId(tag.split(' ').join('_'));
	var constraintDiv = getTagSearchDisplay(tag);
	//disableAjaxAlert = false;
	editInProgress = false;
	tagInEdit = null;
	select_tags = null;
	confirmQueryEditDialog.remove();
	confirmQueryEditDialog = null;
	$('#queryDiv').html('');
	$('#queryDiv').css('display', 'none');
	showPreview();
}

function addToQueryDiv(tag, count) {
	var tagId = makeId(tag.split(' ').join('_'));
	var div = $('#' + makeId('queryDiv', tagId));
	$('.orphan').remove();
	var tableWrapper = tagTableWrapper(tag);
	tableWrapper.css('display', 'none');
	div.append(tableWrapper);
	addToQueryTable(makeId(tagId, 'searchTable', FIELDSET_COUNTER), tag);
	tableWrapper.css('display', '');
	return div;
}

function tagQueryDiv(tag) {
	var tagId = makeId(tag.split(' ').join('_'));
	var div = $('<div>');
	div.attr({	id: makeId('queryDiv', tagId),
				tag: tag });
	div.addClass('dialogfont');
	div.css('display', 'none');
	return div;
}

function tagTableWrapper(tag) {
	var tagId = makeId(tag.split(' ').join('_'));
	var tableWrapper = $('<table>');
	tableWrapper.attr('id', makeId('queryTableWrapper', ++FIELDSET_COUNTER));
	var tbodyWrapper = $('<tbody>');
	tableWrapper.append(tbodyWrapper);
	var trWrapper = $('<tr>');
	trWrapper.attr('id', makeId('queryFiledset', FIELDSET_COUNTER));
	tbodyWrapper.append(trWrapper);
	var tdWrapper = $('<td>');
	trWrapper.append(tdWrapper);
	var fieldset = $('<fieldset>');
	tdWrapper.append(fieldset);
	var table = $('<table>');
	fieldset.append(table);
	table.addClass('displayQuery');
	table.attr({	id: makeId(tagId, 'searchTable', FIELDSET_COUNTER),
					border: '0',
					cellpadding: '0',
					cellspacing: '0' });
	var thead = $('<thead>');
	table.append(thead);
	var tr = $('<tr>');
	thead.append(tr);
	var th = $('<th>');
	tr.append(th);
	th.html('&nbsp;&nbsp;Operator&nbsp;&nbsp;');
	th = $('<th>');
	tr.append(th);
	th.html('&nbsp;&nbsp;Values&nbsp;&nbsp;');
	var tbody = $('<tbody>');
	table.append(tbody);
	tdWrapper = $('<td>');
	tdWrapper.attr('valign', 'top');
	trWrapper.append(tdWrapper);
	var img = $('<img>');
	img.attr({	src: HOME + '/static/plus.png',
				width: '16',
				height: '16',
				alt: '+' });
	img.click({	tag: tag,
				count: FIELDSET_COUNTER },
				function(event) {addToQueryDiv(event.data.tag, event.data.count);});
	tdWrapper.append(img);
	tdWrapper = $('<td>');
	tdWrapper.attr('valign', 'top');
	trWrapper.append(tdWrapper);
	img = $('<img>');
	img.attr({	src: HOME + '/static/minus.png',
				width: '16',
				height: '16',
				alt: '-' });
	img.click({	rowId: makeId('queryFiledset', FIELDSET_COUNTER),
				tableId: makeId('queryTableWrapper', FIELDSET_COUNTER),
				tagId: tagId}, 
				function(event) {deleteConstraintRow(event.data.rowId, event.data.tableId, event.data.tagId);});
	tdWrapper.append(img);
	return tableWrapper;
}

function getTagSearchDisplay(tag) {
	var divConstraint = $('<div>');
	divConstraint.attr('ALIGN', 'LEFT');
	var table = $('<table>');
	divConstraint.append(table);
	if (queryFilter[tag] != null) {
		$.each(queryFilter[tag], function(i, item) {
			var tr = $('<tr>');
			table.append(tr);
			var td = $('<td>');
			tr.append(td);
			var val = item['opUser'] == 'Between' ? '=' : item['op'];
			val = val == null ? ':tagged:' : val;
			switch (item['vals'].length) {
			case 0:
				break;
			case 1:
				val += ' ' + item['vals'][0];
				break;
			default:
				val += item['opUser'] == 'Between' ? '(' : '{';
				val += item['vals'].join(',');
				val += item['opUser'] == 'Between' ? ')' : '}';
				break;
				
			}
			td.html(val);
		});
	}
	divConstraint.click({	tag: tag },
							function(event) {event.preventDefault(); editQuery(event.data.tag);});
	return divConstraint;
}

function saveTagPredicate(tag, div) {
	queryFilter[tag] = new Array();
	var divTables = div.children();
	$.each(divTables, function(i, divTable) {
		var tbody = getChild($(divTable), 1);
		var tr = getChild(tbody, 1);
		td = getChild(tr, 1);
		var fieldset = getChild(td, 1);
		var table = getChild(fieldset, 1);
		tbody = getChild(table, 2);
		tr = getChild(tbody, 1);
		td = getChild(tr, 1);
		var op = getChild(td, 1).val();
		if (op == 'Between') {
			td = getChild(tr, 2);
			var table = getChild(td, 1);
			var tbody = getChild(table, 1);
			var tr = getChild(tbody, 1);
			var td = getChild(tr, 1);
			var val1 = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
			td = getChild(tr, 3);
			var val2 = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
			if (val1 != '' && val2 != '') {
				var pred = new Object();
				pred['opUser'] = op;
				pred['vals'] = new Array();
				pred['vals'].push(val1);
				pred['vals'].push(val2);
				queryFilter[tag].push(pred);
			}
		} else if (op != 'Tagged' && op != 'Tag absent') {
			// values column
			var td = getChild(tr, 2);
			var table = getChild(td, 1);
			var tbody = getChild(table, 1);
			var values = new Array();
			$.each(tbody.children(), function(j, row) {
				td = getChild($(row), 1);
				var input = getChild(td, 1);
				var val = input.val().replace(/^\s*/, "").replace(/\s*$/, "");
				if (val.length > 0) {
					values.push(val);
				}
			});
			if (values.length > 0) {
				var pred = new Object();
				pred['opUser'] = op;
				pred['op'] = ops[op];
				pred['vals'] = values;
				queryFilter[tag].push(pred);
			}
		} else if (op == 'Tagged') {
			var pred = new Object();
			pred['opUser'] = op;
			pred['vals'] = new Array();
			queryFilter[tag].push(pred);
		} else {
			var pred = new Object();
			pred['opUser'] = op;
			pred['op'] = ops[op];
			pred['vals'] = new Array();
			queryFilter[tag].push(pred);
		}
	});
	if (queryFilter[tag].length == 0) {
		delete queryFilter[tag];
	}
}

function addFilterToQueryTable(tag) {
	var tagId = makeId(tag.split(' ').join('_'));
	var div = $('#queryDiv');
	div.css('display', '');
	var tagDiv = tagQueryDiv(tag);
	div.append(tagDiv);
	if (queryFilter[tag] != null) {
		$.each(queryFilter[tag], function(i, pred) {
			addToQueryDiv(tag, ++FIELDSET_COUNTER);
			var tableId = makeId(tagId, 'searchTable', FIELDSET_COUNTER);
			var tbody = getChild($('#' + tableId), 2);
			var tr = getChild(tbody, 1);
			var td = getChild(tr, 1);
			var select = getChild(td, 1);
			var tableTbody = getChild($('#' + tableId), 2).find('tbody');
			if (tableTbody.get(0) != null) {
				$.each(tableTbody.children(), function(i, tr) {
					$(tr).remove();
				});
			}
			select.val(pred['opUser']);
			if (availableTags[tag] != 'empty') {
				if (pred['opUser'] == 'Between') {
					var selId = select.attr('id');
					addNewValue(ROW_COUNTER, availableTags[tag], selId, tag, pred['vals']);
					var valTbody = getChild($('#' + tableId), 2).find('tbody');
					var valTr = getChild(valTbody, 1);
					var valTd = getChild(valTr, 1);
					var input1 = getChild(valTd, 1);
					input1.val(pred['vals'][0]);
					valTd = getChild(valTr, 3);
					var input2 = getChild(valTd, 1);
					input2.val(pred['vals'][1]);
				} else if (pred['opUser'] != 'Tagged' && pred['opUser'] != 'Tag absent') {
					var selId = select.attr('id');
					$.each(pred['vals'], function(j, value) {
						var arr = new Array();
						arr.push(value);
						addNewValue(ROW_COUNTER, availableTags[tag], selId, tag, arr);
						var valTbody = getChild($('#' + tableId), 2).find('tbody');
						var row = getChild(valTbody, j+1);
						var valTd = getChild(row, 1);
						var input = getChild(valTd, 1);
						input.val(value);
					});
				} else {
					var thead = getChild($('#' + tableId), 1);
					var thTr = getChild(thead, 1);
					var th = getChild(thTr, 2);
					th.css('display', 'none');
					var td = getChild(tr, 2);
					td.css('display', 'none');
				}
			}
		});
	} else {
		addToQueryDiv(tag, ++FIELDSET_COUNTER);
	}
	tagDiv.css('display', '');
	var width = 0;
	var height = 0;
	for (var i=0; i<tagDiv.children().length; i++) {
		var tbody = getChild(tagDiv, i+1).find('tbody');
		var crtWidth = tbody.width();
		if (crtWidth > width) {
			width = crtWidth;
		}
		height += tbody.height() + 10;
	}
	width += 100;
	height += 200;
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
		height: height,
		modal: false,
		resizable: true,
		width: width,
		beforeClose: function(event, ui) {cancelEdit(tag);}
	});
	confirmQueryEditDialog.dialog('open');
}

/**
 * Returns the locale string of a timestamp having the format 'yyyy-mm-dd hh:mm:ss[.llllll]{+|-}HH:MM'.
 * .llllll represents microseconds and is optional
 * the last part represents the timezone offset and it has the + or - sign followed by the number of hours and minutes
 * Example: '2011-12-02 09:33:34.784133-08:00'
 */
function getLocaleTimestamp(s) {
	var values = s.split(' ');
	var localValues = values[0].split('-');
	var date = (new Date(parseInt(localValues[0], 10), parseInt(localValues[1], 10) - 1, parseInt(localValues[2], 10))).getTime();
	var utc = values[1].slice(-6);
	var time = values[1].slice(0, values[1].length - 6);
	var timeValues = time.split('.');
	var ms = 0;
	var msText = '';
	if (timeValues.length > 1) {
		msText = '.' + timeValues[1];
		ms = Math.floor(parseInt(timeValues[1]) / 1000, 10);
	}
	var hms = timeValues[0].split(':');
	var hours = parseInt(hms[0], 10);
	var minutes = parseInt(hms[1], 10);
	var seconds = parseInt(hms[2], 10);
	var utcValues = utc.split(':');
	var utcDelta = (new Date()).getTimezoneOffset() + parseInt(utcValues[0], 10) * 60 + parseInt(utcValues[1], 10);
	date += hours * 60 * 60 * 1000 +
			(minutes + utcDelta) * 60 * 1000 +
			seconds * 1000 +
			ms;
	var newDate = new Date(date);
	var ret = 	newDate.getFullYear() + '-' +
				('0' + (newDate.getMonth() + 1)).slice(-2) + '-' +
				('0' + newDate.getDate()).slice(-2) + ' ' +
				('0' + newDate.getHours()).slice(-2) + ':' +
				('0' + newDate.getMinutes()).slice(-2) + ':' +
				('0' + newDate.getSeconds()).slice(-2) +
				msText;
	return ret;
	
}

function setTimepickerOptions(input, dp_inst, tp_inst){
	var now = new Date();
	tp_inst.hour = now.getHours();
	tp_inst.minute = now.getMinutes();
	tp_inst.second = now.getSeconds();
	tp_inst.millisec = now.getMilliseconds();
}

function initIdleWarning() {
	$('#Idle_Session_Warning').css('display', '');
	confirmLogoutDialog = $('#Idle_Session_Warning');
	confirmLogoutDialog.dialog({
		autoOpen: false,
		title: 'Idle Session Warning',
		buttons: {
			"Log out now": function() {
					runLogoutRequest();
					$(this).dialog('close');
				},
			"Extend session": function() {
					runExtendRequest();
					setExtendTime();
					$(this).dialog('close');
				}
		},
		draggable: false,
		modal: true,
		resizable: false,
		width: 350,
		beforeClose: function(event, ui) {warn_window_is_open = false;}
	});
}

