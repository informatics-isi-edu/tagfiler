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

    if (subject['Image Set']) {
		results.dtype = 'Image Set';
    }
    else if (subject['template mode']) {
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
	node.innerHTML = d;
    }
}

/**
 * Runs the session poll - argument is in minutes
 *
 */
function runSessionPolling(pollmins, warnmins) {
    expiration_poll_mins = pollmins;
    expiration_warn_mins = warnmins;
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
    timer = setTimeout("startSessionTimer("+t+")", t);
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
	kv = cookies[c].replace(/^\s*/, "").replace(/\s*$/, "").split("=");
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

function runLogoutRequest() {
	userLogout();
}

function runExtendRequest() {
    if (ajax_request) {
	if (ajax_request.readystate != 0) {
	    ajax_request.abort();
	}
    ajax_request.open("PUT", expiration_check_url);
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
    	window.location = '/tagfiler';
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
		if(ajax_request.status == 200) {
			var session_opts = $.parseJSON(ajax_request.responseText);
			var until = getLocaleTimestamp(session_opts.expires);
			until = until.split(" ")[1].split('.')[0];
			setLocaleDate("untiltime", until);
			var secsremain = session_opts.seconds_remaining;
			if (secsremain < 1) {
				secsremain = 1;
			}
			if ( secsremain < expiration_warn_mins * 60) {
				if (!expiration_warning) {
					startExtendSessionTimer(1000);
					return;
				}
				if (!warn_window_is_open) {
					warn_window_is_open = true;
					confirmLogoutDialog.dialog('open');
					$('.ui-widget-overlay').css('opacity', 1.0);
				}
				startSessionTimer(secsremain * 1000);
			} else {
				startSessionTimer((secsremain - (expiration_warn_mins * 60)) * 1000);
			}
			return;
		} else {
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
 * Set the Dataset Version
 */
function setVersion(value) {
	document.getElementById("Version").value = value;
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
			homePage();
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
var expiration_check_url = "/tagfiler/session";
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
			   "subject" : "subject owner or subject ACL members", 
			   "subjectowner" : "subject owner",
			   "tag" : (ownerand + "tag ACL members"),
			   "system" : "no access",
			   "tagorsubject" : (ownerand + "tag ACL members, subject owner, or subject ACL members"),
			   "tagandsubject" : (ownerand + "tag ACL members who are also either subject owner or subject ACL members"),
			   "tagorowner" : (ownerand + "tag ACL members or subject owner"),
			   "tagandowner" : (ownerand + "tag ACL members who are also subject owner") };
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
		break;
	case 401:		// Unauthorized
		var err = jqXHR.getResponseHeader('X-Error-Description');
		if (err != null) {
			err = decodeURIComponent(err);
			if (err == 'The requested tagfiler API usage by unauthorized client requires authorization.') {
				window.location = '/tagfiler';
				return false;
			}
		}
		break;
	case 403:	// Forbidden
		var err = jqXHR.responseText;
		if (err == 'unauthenticated session access forbidden') {
			window.location = '/tagfiler';
			return false;
		}
		break;
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
		url = home + '/session';
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
			if (typestr == 'role') {
				data = data.attributes;
			}
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
var MULTI_VALUED_ROW_COUNTER;
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
var ops = {
	    'Tagged': '',
	    'Tag absent': ':absent:',
	    'Equal': '=',
	    'Not equal': '!=',
	    'Less than': ':lt:',
	    'Less than or equal': ':leq:',
	    'Greater than': ':gt:',
	    'Greater than or equal': ':geq:',
	    'LIKE (SQL operator)': ':like:',
	    'SIMILAR TO (SQL operator)': ':simto:',
	    'Regular expression (case sensitive)': ':regexp:',
	    'Negated regular expression (case sensitive)': ':!regexp:',
	    'Regular expression (case insensitive)': ':ciregexp:',
	    'Negated regular expression (case insensitive)': ':!ciregexp:'
		
};

var opsExcludeTypes = {
	    '': [],
	    ':regexp:': ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean'],
	    ':!ciregexp:': ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean'],
	    ':!regexp:': ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean'],
	    ':lt:': ['empty', 'boolean'],
	    '=': ['empty'],
	    ':simto:': ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean'],
	    ':ciregexp:': ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean'],
	    ':gt:': ['empty', 'boolean'],
	    ':absent:': [],
	    ':leq:': ['empty', 'boolean'],
	    ':like:': ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean'],
	    '!=': ['empty'],
	    ':geq:': ['empty', 'boolean']
};
var typedefSubjects = null;

var resultColumns = [];
var viewListTags = new Object();
var disableAjaxAlert = false;
var sortColumnsArray = new Array();
var editInProgress = false;
var tagInEdit = null;
var saveSearchConstraint;
var tagToMove = null;
var editCellInProgress = false;
var editBulkInProgress = false;
var clickedCancelOK = false;
var enabledEdit = false;
var displayRangeValues = false;

var confirmQueryEditDialog = null;
var confirmAddTagDialog = null;
var confirmAddMultipleTagsDialog = null;
var confirmTagValuesEditDialog = null;
var confirmTagValuesDeleteDialog = null;

var editTagValuesTemplate = null;
var deleteTagValuesTemplate = null;

var queryFilter = new Object();
var saveQueryFilter = null;
var rangeQueryFilter = null;
var lastSaveQueryFilter = null;
var lastRangeQueryFilter = null;
var predicateTable = null;
var savePredicateFilter = null;
var queryBasePath = null;

var columnRangeValues = new Object;
var headerRangeValues = new Object();

var dragAndDropBox;
var tipBox;

var movePageX;

var SELECT_LIMIT = 50;
var WINDOW_TAB = 0;
var PREVIEW_LIMIT;
var LAST_PREVIEW_LIMIT;
var select_tags = null;
var select_tags_count = null;

var lastPreviewURL = null;
var lastEditTag = null;

var probe_tags;
var enabledDrag = true;
var userOp = new Object();
var localeTimezone;

var intervalPattern = new RegExp('\\((.+),(.+)\\)');

var bulk_value_edit = false;
var cell_value_edit = false;
var file_download = false;
var view_tags = false;
var view_URL = false;

function setRangeValues(range, columnRange, tag) {
	var theadRange = $('#Query_Preview_range');
	if (columnRange == null) {
		//theadRange.hide('slow');
	}
	var trRange = getChild(theadRange, 1);
	if (columnRange != null) {
		var column = columnRange.attr('tag');
		if (range[column] != null) {
			columnRangeValues[column] = range[column];
			appendColumnRangeValues(columnRange);
		} else {
			columnRangeValues[column] = new Array();
			columnRange.html('&nbsp;');
		}
	} else {
		headerRangeValues[tag] = range[tag];
		if (queryFilter[tag] == null) {
			columnRangeValues[tag] = headerRangeValues[tag];
		}
		var iCol = -1;
		$.each(resultColumns, function(i, column) {
			if (tag == column) {
				iCol = i;
				return false;
			}
		});
		iCol += 2;
		var tdRange = getChild(trRange, iCol);
		tdRange.css('white-space', 'nowrap');
		if (tdRange.attr('rangeClicked')) {
			tdRange.removeAttr('rangeClicked');
			replaceColumnRangeValues(tdRange);
		} else {
			if (range[tag] != null) {
				if (range[tag].length == 1 && range[tag][0] == 'too many values to display') {
					tdRange.html(range[tag][0]);
					tdRange.css('white-space', '');
				} else {
					appendRangeValues(tdRange);
				}
			} else {
				tdRange.html('&nbsp;');
			}
		}
	}
	if (columnRange == null) {
		//theadRange.show('slow');
	}
	document.body.style.cursor = 'default';
}

function initColumnRange(tdRange) {
	tdRange.html('');
	var div = $('<div>');
	tdRange.append(div);
	div = $('<div>');
	tdRange.append(div);
}

function appendDivRange(range, tdRange, div) {
	var column = tdRange.attr('tag');
	var table = $('<table>');
	div.append(table);
	$.each(range[column], function(j, value) {
		var tr = $('<tr>');
		table.append(tr);
		var td = $('<td>');
		tr.append(td);
		td.css('padding', '0px 0px 0px 0px');
		td.attr('tag', column);
		td.attr('originalValue', value);
		td.attr('iRow', j);
		td.html(value);
		if (saveQueryFilter[column] != null) {
			var last = queryFilter[column].length - 1;
			if (queryFilter[column][last]['vals'].contains(value)) {
				td.addClass('range');
			}
		}
		td.click({	td: td },
					function(event) {rangeFilter(event, event.data.td);});
	});
}

function appendRangeValues(tdRange) {
	initColumnRange(tdRange);
	appendDivRange(headerRangeValues, tdRange, getChild(tdRange, 1));
	var column = tdRange.attr('tag');
	if (columnRangeValues[column] != null) {
		appendDivRange(columnRangeValues, tdRange, getChild(tdRange, 2));
	}
	getChild(tdRange, 2).css('display', 'none');
}

function appendColumnRangeValues(tdRange) {
	var column = tdRange.attr('tag');
	var div1 = getChild(tdRange, 1);
	var div2 = getChild(tdRange, 2);
	appendDivRange(columnRangeValues, tdRange, div2);
	div1.css('display', 'none');
	div2.css('display', '');
}

function replaceColumnRangeValues(tdRange) {
	var column = tdRange.attr('tag');
	var div = getChild(tdRange, 1);
	div.html('');
	appendDivRange(headerRangeValues, tdRange, div);
	// adjust new values
	var div2 = getChild(tdRange, 2);
	var trs = div2.find('tr');
	$.each(trs, function(j, tr) {
		var td = getChild($(tr), 1);
		var value = td.attr('originalValue');
		td.html(value);
	});
}

function loadRange(tdRange) {
	if (tdRange != null) {
		var tag = tdRange.attr('tag');
		loadTagRange(tdRange, tag, true);
	} else {
		$.each(resultColumns, function(i, tag) {
			loadTagRange(tdRange, tag, false);
		});
	}
}

function loadTagRange(tdRange, tag, exclude) {
	document.body.style.cursor = 'wait';
	var range = new Object();
	var predUrl = HOME + '/query' + queryBasePath + getQueryPredUrl(exclude ? tag : '');
	var columnArray = new Array();
	columnArray.push(tag);
	queryUrl = getQueryUrl(predUrl, '&range=count', encodeURIArray(columnArray, ''), new Array(), '');
	$.ajax({
		url: queryUrl,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
		success: function(data, textStatus, jqXHR) {
			var columnArray = new Array();
			$.each(data[0], function(key, value) {
				if (value == 0) {
					range[key] = null;
				} else if (value <= SELECT_LIMIT) {
					columnArray.push(key);
				} else {
					var rangeArray = new Array();
					rangeArray.push('too many values to display');
					range[key] = rangeArray;
				}
			});
			if (columnArray.length == 0) {
				setRangeValues(range, tdRange, tag);
			} else {
				// if we want sorted by frequency ascended use '&range=values' + encodeSafeURIComponent('<') or
				// descending use '&range=values' + encodeSafeURIComponent('>')
				queryUrl = getQueryUrl(predUrl, '&range=values', encodeURIArray(columnArray, ''), new Array(), '');
				$.ajax({
					url: queryUrl,
					headers: {'User-agent': 'Tagfiler/1.0'},
					async: true,
					accepts: {text: 'application/json'},
					dataType: 'json',
					success: function(data, textStatus, jqXHR) {
						$.each(data[0], function(key, value) {
							range[key] = value;
						});
						setRangeValues(range, tdRange, tag);
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

function setGUIConfig() {
	var url = HOME + '/query/config=tagfiler(' + encodeSafeURIComponent('_cfg_enabled GUI features') + ')';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			var values = data[0]['_cfg_enabled GUI features'];
			if (values != null) {
				if (values.contains('bulk_value_edit')) {
					bulk_value_edit = true;
				}
				if (values.contains('cell_value_edit')) {
					cell_value_edit = true;
					$('#enableEdit').css('display', '');
				}
				if (values.contains('file_download')) {
					file_download = true;
				}
				if (values.contains('view_tags')) {
					view_tags = true;
				}
				if (values.contains('view_URL')) {
					view_URL = true;
				}
			} else {
				bulk_value_edit = true;
				cell_value_edit = true;
				$('#enableEdit').css('display', '');
				file_download = true;
				view_tags = true;
				view_URL = true;
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			// ignore for now until the tag will be defined 'enabled GUI features'
			//handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

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
	saveQueryFilter = new Object();
	rangeQueryFilter = new Object();
	$('#GlobalMenu').slideUp('slow');
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
		alert('Warning: No values available for the operator.');
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
	
	var theadRange = $('#Query_Preview_range');
	var trRange = getChild(theadRange, 1);
	var col1 = getChild(trRange, index1 + 2);
	var col2 = getChild(trRange, index2 + 2);
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
			var col = getChild(trRange, resultColumns.length+1);
			col.removeClass('separator');
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
	var tr1 = thead.find('.sortAndContextMenu');
	var tr2 = thead.find('.columnName');;
	var tr3 = thead.find('.columnFilter');;
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
	var predUrl = HOME + '/query' + queryBasePath + getQueryPredUrl('');
	var offset = '&offset=' + PAGE_PREVIEW * PREVIEW_LIMIT;
	var queryUrl = getQueryUrl(predUrl, '&limit=' + PREVIEW_LIMIT, encodeURIArray(resultColumns, ''), encodeURISortArray(), offset);
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
	if (header.offset() == null) {
		return;
	}
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

function accessNextPage() {
	PAGE_PREVIEW = parseInt($('#showResultRange').val());
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

function initPSOC_old(home, user, webauthnhome, basepath, querypath) {
	alert(basepath);
	alert(querypath);
	var querypathJSON = null;
	if (querypath != null) {
		querypathJSON = $.parseJSON( querypath );
	}
	initPSOC(home, user, webauthnhome, basepath, querypathJSON);
}

function initPSOC(home, user, webauthnhome, basepath, querypathJSON) {
	//alert(basepath);
	//alert(querypath);
	HOME = home;
	USER = user;
	WEBAUTHNHOME = webauthnhome;
	ROW_COUNTER = 0;
	MULTI_VALUED_ROW_COUNTER = 0;
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
	resultColumns = [];
	userOp = new Object();
	queryFilter = new Object();
	sortColumnsArray = new Array();
	availableTags = null;
	availableTagdefs = null;
	allTagdefs = null;
	availableViews = null;
	lastPreviewURL = null;
	
	queryBasePath = basepath;
	if (queryBasePath != '/') {
		queryBasePath += '/';
	}
	initPreview();
	setGUIConfig();
	
	editTagValuesTemplate = $('#editTagValuesDiv');
	deleteTagValuesTemplate = $('#deleteTagValuesDiv');

	$.ajaxSetup({ cache: true });
	
	// build the userOp dictionary
	$.each(ops, function(key, value) {
		userOp[value] = key;
	});
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
		if (ret) {
			if (ret['tag'] == null) {
				HideDragAndDropBox();
				tagToMove = null;
			} else {
				dropColumn(e, ret['tag'], ret['append']);
			}
		}
	});
	loadTags();
	if (querypathJSON != null) {
		var last = querypathJSON.length - 1;
		if (last < 0) {
			last = 0;
		}
		var lpreds = querypathJSON[last]['lpreds'];
		$.each(lpreds, function(i, pred) {
			resultColumns.push(pred['tag']);
		});
		var spreds = querypathJSON[last]['spreds'];
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
		var otags = querypathJSON[last]['otags'];
		$.each(otags, function(i, item) {
			var sortObject = new Object();
			sortObject['name'] = item[0];
			sortObject['direction'] = item[1];
			sortObject['index'] = '' + (i + 1);
			sortColumnsArray.push(sortObject);
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
		title: 'Show another column',
		buttons: {
			'Cancel': function() {
					$(this).dialog('close');
				},
			'Add to query': function() {
					addToListColumns('customizedViewSelect');
				}
		},
		draggable: true,
		position: 'top',
		height: ($(window).height() < 300 ? $(window).height() : 300),
		modal: false,
		resizable: true,
		width: ($(window).width() < 450 ? $(window).width() : 450)
	});
	$('#selectViewDiv').css('display', '');
	confirmAddMultipleTagsDialog = $('#selectViewDiv');
	confirmAddMultipleTagsDialog.dialog({
		autoOpen: false,
		title: 'Show columns from a view',
		buttons: {
			'Cancel': function() {
					$(this).dialog('close');
				},
			'Add to query': function() {
					addViewToListColumns('selectViews');
				}
		},
		draggable: true,
		position: 'top',
		height: ($(window).height() < 300 ? $(window).height() : 300),
		modal: false,
		resizable: true,
		width: ($(window).width() < 450 ? $(window).width() : 450)
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
			var results = ['bytes', 'vname', 'url', 'template%20mode', 'id', 'Image%20Set'];
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
			td.css('padding', '0px 0px 0px 0px');
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
			td.css('padding', '0px 0px 0px 0px');
			td.append('AND');
			td = $('<td>');
			tr.append(td);
			td.css('border-width', '0px');
			td.css('padding', '0px 0px 0px 0px');
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
			td.css('padding', '0px 0px 0px 0px');
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
			td.css('padding', '0px 0px 0px 0px');
			tr.append(td);
			td.append('AND');
			td = $('<td>');
			td.css('padding', '0px 0px 0px 0px');
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
		td.css('padding', '0px 0px 0px 0px');
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
		td.css('padding', '0px 0px 0px 0px');
		tr.append(td);
		td.css('border-width', '0px');
		if (values != null && !hasTagValueOption(tag, values[0]) || select_tags_count[tag] != null) {
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
		td.css('padding', '0px 0px 0px 0px');
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
		td.css('padding', '0px 0px 0px 0px');
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
	bindDateTimePicker();
	bindDatePicker();
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

function encodeURISortArray() {
	var ret = new Array();
	$.each(sortColumnsArray, function(i, column) {
		ret.push(encodeSafeURIComponent(column['name']) + column['direction']);
	});
	return ret;
}

function getQueryPredUrl(excludeTag) {
	if (tagInEdit != null && editInProgress) {
		var tagConstraintDiv = $('#' +makeId('queryDiv', tagInEdit.split(' ').join('_')));
		saveTagPredicate(tagInEdit, tagConstraintDiv);
	}
	if (predicateTable != null) {
		updateTagPredicate();
	}
	var query = new Array();
	var url = '';
	$.each(queryFilter, function(tag, preds) {
		if (tag == tagInEdit && !editInProgress || tag == excludeTag) {
			return true;
		}
		var suffix = '';
		if (availableTags[tag] == 'timestamptz') {
			suffix = localeTimezone;
		}
		$.each(preds, function(i, pred) {
			if (pred['opUser'] != 'None') {
				if (pred['opUser'] == 'Between') {
					query.push(encodeSafeURIComponent(tag) + '=' + encodeSafeURIComponent('(' + pred['vals'][0] + suffix + ',' +
																	pred['vals'][1] + suffix + ')'));
				} else if (pred['opUser'] != 'Tagged' && pred['opUser'] != 'Tag absent') {
					query.push(encodeSafeURIComponent(tag) + pred['op'] + encodeURIArray(pred['vals'], suffix).join(','));
				} else {
					query.push(encodeSafeURIComponent(tag) + (pred['op'] != null ? pred['op'] : ''));
				}
			}
		});
	});
	if (query.length > 0) {
		url = query.join(';');
	}
	return url;
}

function getQueryUrl(predUrl, limit, encodedResultColumns, encodedSortedColumns, offset) {
	var retTags = '(' + encodedResultColumns.join(';') + ')';
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
	if (column == '') {
		alert('Please select an available tag.');
		return;
	}
	confirmAddTagDialog.dialog('close');
	var choice = $('input:radio[name=showAnotherColumn]:checked').val();
	if (choice == 'replace') {
		resultColumns = new Array();
		sortColumnsArray = new Array();
		queryFilter = new Object();
	}
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
	var predUrl = HOME + '/query' +queryBasePath + getQueryPredUrl('');
	var queryUrl = getQueryUrl(predUrl, limit, encodeURIArray(resultColumns, ''), encodeURISortArray(), offset);
	if (!editBulkInProgress && lastPreviewURL == queryUrl && lastEditTag == tagInEdit && PREVIEW_LIMIT == LAST_PREVIEW_LIMIT) {
		return;
	}
	document.body.style.cursor = 'wait';
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
	var predUrl = HOME + '/query' + queryBasePath + getQueryPredUrl('');
	var totalRows = 0;
	var columnArray = new Array();
	columnArray.push(tag);
	queryUrl = getQueryUrl(predUrl, '&range=count', encodeURIArray(columnArray, ''), new Array(), '');
	select_tags = new Object();
	select_tags_count = new Object();
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
			} else {
				select_tags_count[tag] = totalRows;
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
	var queryUrl = getQueryUrl(predUrl, limit == '' ? '&limit=' + (PREVIEW_LIMIT != -1 ? PREVIEW_LIMIT : 'none') : limit, encodeURIArray(predList, ''), encodeURISortArray(), offset);
	var queryPreview = $('#Query_Preview');
	var table = getChild(queryPreview, 1);
	if (table.get(0) == null) {
		table = $('<table>');
		table.addClass('display');
		table.attr({	border: '0',
						cellpadding: '0',
						cellspacing: '0' });
		queryPreview.append(table);
		var theadRange = $('<thead>');
		theadRange.css('display', displayRangeValues ? '' : 'none');
		theadRange.css('background-color', '#EBEBEB');
		table.append(theadRange);
		theadRange.attr('id', 'Query_Preview_range');
		var trRange = $('<tr>');
		theadRange.append(trRange);
		var thead = $('<thead>');
		thead.css('background-color', '#F2F2F2');
		table.append(thead);
		thead.attr('id', 'Query_Preview_header');
		var tr = $('<tr>');
		tr.addClass('sortAndContextMenu');
		thead.append(tr);
		tr = $('<tr>');
		tr.addClass('columnName');
		thead.append(tr);
		tr = $('<tr>');
		tr.addClass('columnFilter');
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
	var theadRange = getChild(table, 1);
	var thead = getChild(table, 2);
	var tfoot = getChild(table, 4);
	var tr1 = thead.find('.sortAndContextMenu');
	var tr2 = thead.find('.columnName');
	var tr3 = thead.find('.columnFilter');
	var trfoot = getChild(tfoot, 1);
	var trRange = getChild(theadRange, 1);
	if (getChild(tr1, 1).get(0) == null) {
		// first column for context menu
		var tdRange = $('<td>');
		tdRange.attr('width', '1%');
		tdRange.css('background-color', 'white');
		trRange.append(tdRange);
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
			var tdRange = $('<td>');
			tdRange.css('white-space', 'nowrap');
			tdRange.addClass('separator');
			tdRange.addClass('rangeHeader');
			tdRange.attr('valign', 'top');
			trRange.append(tdRange);

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
				var tdRange = getChild(trRange, i+2);
				tdRange.addClass('separator');
			}
		} else {
			if (td.hasClass('separator')) {
				td.removeClass('separator');
				td = getChild(tr2, i+2);
				td.removeClass('separator');
				td = getChild(tr3, i+2);
				td.removeClass('separator');
				var tdRange = getChild(trRange, i+2);
				tdRange.removeClass('separator');
			}
		}
		var tdRange = getChild(trRange, i+2);
		tdRange.css('display', '');
		tdRange.attr('tag', column);
		tdRange.attr('iCol', '' + i);
		var columSortId = makeId('sort', column.split(' ').join('_'), PREVIEW_COUNTER);
		var tdSort = getChild(tr1, i+2);
		tdSort.css('display', '');
		tdSort.html('');
		tdSort.attr('id', columSortId);
		tdSort.attr('iCol', '' + (i+1));
		var sortValue = getSortOrder(column);
		var label = $('<label>');
		tdSort.append(label);
		if (sortValue != null) {
			label.html(sortValue['index']);
			var content;
			var direction = (sortValue['direction'] == ':asc:') ? 'ascending order' : 'descending order';
			switch(parseInt(sortValue['index'])) {
				case 1:
					content = 'First sorted column: ' + direction;
					break;
				case 2:
					content = 'Second sorted column: ' + direction;
					break;
				default:
					content = 'n-th sorted column: ' + direction;
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
		li.addClass('item addFilter');
		li.html('Add filter');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {event.preventDefault(); addFilter(column, -1);});
		if (predicateTable != null) {
			li.css('display', 'none');
		}
		ul.append(li);

		li = $('<li>');
		li.addClass('item clearColumnFilter');
		li.html('Clear column filter');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {clearFilter(column);});
		ul.append(li);
		if (queryFilter[column] == null) {
			li.css('display', 'none');
		}
		li = $('<li>');
		li.addClass('item editColumnFilter');
		li.html('Edit column filter...');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {event.preventDefault(); editQuery(column);});
		if (predicateTable != null) {
			li.css('display', 'none');
		}
		ul.append(li);

		if (bulk_value_edit) {
			li = $('<li>');
			li.addClass('item editValue');
			li.html('Edit column values...');
			li.mouseup(function(event) {event.preventDefault();});
			li.mousedown(function(event) {event.preventDefault(); editTagValues(column);});
			ul.append(li);
		}
		
		li = $('<li>');
		li.addClass('item deleteColumn');
		li.html('Hide column');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {deleteColumn(column, PREVIEW_COUNTER);});
		ul.append(li);
		if (resultColumns.length <= 1) {
			li.css('display', 'none');
		}
		
		li = $('<li>');
		li.addClass('item sortAscending');
		li.html('Sort column ascending');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {sortColumn(column, columSortId, PREVIEW_COUNTER, ':asc:');});
		ul.append(li);
		if (sortValue != null && sortValue['direction'] == ':asc:') {
			li.css('display', 'none');
		}
		
		li = $('<li>');
		li.addClass('item sortDescending');
		li.html('Sort column descending');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {sortColumn(column, columSortId, PREVIEW_COUNTER, ':desc:');});
		ul.append(li);
		if (sortValue != null && sortValue['direction'] == ':desc:') {
			li.css('display', 'none');
		}
		
		li = $('<li>');
		li.addClass('item unsort');
		li.html('Unsort column');
		li.mouseup(function(event) {event.preventDefault();});
		li.mousedown(function(event) {sortColumn(column, columSortId, PREVIEW_COUNTER, 'unsort');});
		ul.append(li);
		if (sortValue == null) {
			li.css('display', 'none');
		}
		
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
		if (predicateTable == null || predicateTable.attr('tag') != column) {
			td3.css('display', '');
			td3.attr('iCol', '' + (i+1));
			var divConstraint = getChild(td3, 1);
			divConstraint.attr('id', makeId('constraint', column.split(' ').join('_'), PREVIEW_COUNTER));
			divConstraint.html('');
			if (queryFilter[column] != null) {
				var constraint = getTagSearchDisplay(column);
				divConstraint.append(constraint);
			}
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
		td = getChild(trRange, i+1);
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
			var tbody = getChild(table, 3);
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
				tr.attr('recordId', row['id'])
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
					td.unbind();
					if (enabledEdit) {
						td.click({	td: td,
									column: column,
									id: row['id'] },
									function(event) {editCell(event.data.td, event.data.column, event.data.id);});
					}
					td.removeClass();
					td.addClass(column.replace(/ /g, ''));
					td.addClass('tablecell');
					if (j < (resultColumns.length - 1)) {
						td.addClass('separator');
					}
					td.attr('iCol', '' + (j+1));
					td.attr('tag', column);
					td.html('');
					if (row[column] != null) {
						if (!allTagdefs[column]['tagdef multivalue']) {
							if (row[column] === true && availableTags[column] == 'empty') {
								td.html('is set');
							} else if (row[column] === false && availableTags[column] == 'empty') {
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
							td.html(row[column].join('<br>'));
						}
					} else {
						td.addClass('tablecelledit');
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
				b.html('No matches');
				$('#pagePrevious').css('display', 'none');
				$('#resultsRange').html('');
				$('#pageNext').css('display', 'none');
				$('#totalResults').html('');
			} else if (previewRows < totalRows) {
				var minRow = 1;
				if (offset != '') {
					offset = parseInt(offset.split('=')[1]);
					minRow = offset + 1;
				}
				var maxRow = minRow + PREVIEW_LIMIT - 1;
				if (maxRow > totalRows) {
					maxRow = totalRows;
				}
				b.html('Showing ');
				getSelectRange(totalRows);
				if (minRow > PREVIEW_LIMIT) {
					$('#pagePrevious').css('display', '');
				} else {
					$('#pagePrevious').css('display', 'none');
				}
				if (maxRow < totalRows) {
					$('#pageNext').css('display', '');
				} else {
					$('#pageNext').css('display', 'none');
				}
				$('#totalResults').html('of ' + totalRows + ' matches');
			} else {
				$('#pagePrevious').css('display', 'none');
				$('#pageNext').css('display', 'none');
				b.html('Showing all ' + previewRows + ' matches');
				$('#resultsRange').html('');
				$('#totalResults').html('');
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
			if (displayRangeValues) {
				$('.rangeHeader').unbind('mouseenter mouseleave');
				loadRange(null);
				enableRangeEvents();
			}
			$('td.topnav ul.subnav li.item').click(function(event) {event.preventDefault();});
			$('td.topnav ul.subnav li.item').mouseup(function(event) {event.preventDefault();});
			$('td.topnav span').click(function() {
				enabledDrag = false;
				var ul = $(this).parent().find('ul.subnav');
				if (ul.children().length == 0) {
					fillIdContextMenu(ul);
				}
				var height = $(this).height();
				var top = ($(this).position().top + height) + 'px';
				$('ul.subnav').css('top', top);
				var left = $(this).position().left + $(this).width() - 180;
				if (left < 0) {
					left = 0;
				}
				left += 'px';
				$('ul.subnav').css('left', left);
				
				//Following events are applied to the subnav itself (moving subnav up and down)
				$(this).parent().find('ul.subnav').slideDown('fast').show(); //Drop down the subnav on click
		
				$(this).parent().hover(function() {
				}, function(){	
					$(this).parent().find('ul.subnav').slideUp('slow'); //When the mouse hovers out of the subnav, move it back up
					enabledDrag = true;
				});
		
				//Following events are applied to the trigger (Hover events for the trigger)
				}).hover(function() { 
					$(this).addClass('subhover'); //On hover over, add class 'subhover'
				}, function(){	//On Hover Out
					$(this).removeClass('subhover'); //On hover out, remove class 'subhover'
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
			if (enabledEdit) {
				$('.tablecell').contextMenu({ menu: 'tablecellMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
				$('.tablecelledit').contextMenu({ menu: 'tablecellEditMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
			} else if (cell_value_edit) {
				$('.tablecell').click(function(event) {DisplayTipBox(event, 'You might "Enable edit" via the "Actions" menu.');});
				$('.tablecell').mouseout(function(event) {HideTipBox();});
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (!disableAjaxAlert) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, queryUrl);
			}
		}
	});
	document.body.style.cursor = 'default';
}

function fillIdContextMenu(ul) {
	if (!view_tags && !view_URL && !file_download) {
		return;
	}
	var id = ul.attr('idVal')
	var subject = null;
	var idUrl = HOME + '/query' + queryBasePath + 'id=' + id + '(' + probe_tags + ')';
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
	if (dtype == 'Image Set') {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		var index = results['dataname'].indexOf('@');
		var downloadUrl = 'javascript:downloadStudy("study/name=';
		if (index != -1) {
			var name = results['dataname'].substr(0, index);
			var version = results['dataname'].substr(index+1);
			downloadUrl += encodeSafeURIComponent(name) + ';version=' + encodeSafeURIComponent(version);
		} else {
			downloadUrl += encodeSafeURIComponent(results['dataname']);
		}
		downloadUrl += '?action=download")';
		a.attr({	href: downloadUrl });
		a.html('Download Study ' + results['dataname']);
		dtype = 'url';
	}
	if (dtype == 'template' && view_URL) {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({	target: '_newtab2' + ++WINDOW_TAB,
					href: HOME + '/file/' + results['datapred'] });
		a.html('View ' + results['dataname']);
	} else if (dtype == 'url' && view_URL) {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({	target: '_newtab2' + ++WINDOW_TAB,
					href: subject['url'] });
		a.html('View ' + results['dataname']);
	} else if (dtype == 'file' && file_download) {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({	target: '_newtab2' + ++WINDOW_TAB,
					href: HOME + '/file/' + results['datapred'] });
		a.html('Download ' + results['dataname']);
	}
	if (view_tags) {
		var li = $('<li>');
		ul.append(li);
		var a = $('<a>');
		li.append(a);
		a.attr({href: 'javascript:getTagDefinition("'+ encodeSafeURIComponent(results['datapred']) + '","alltags")' });
		a.html('View tags page');
	}
	if (ul.children().length == 0) {
		var li = $('<li>');
		ul.append(li);
		li.html('No available actions');
	}
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
	if (sort == 'unsort') {
		stopSortColumn(column, count);
		getChild($('#' + id), 1).unbind('mouseenter mouseleave');
	} else {
		var sortObject = getSortOrder(column);
		if (sortObject == null) {
			sortObject = new Object();
			sortColumnsArray.push(sortObject);
			var length = sortColumnsArray.length;
			sortObject['name'] = column;
			sortObject['index'] = '' + length;
			getChild($('#' + id), 1).html('' + length);
		} else {
			sortObject = sortColumnsArray[parseInt(sortObject['index']) - 1];
		}
		sortObject['direction'] = '' + sort;
		var content;
		var direction = (sort == ':asc:') ? 'ascending order' : 'descending order';
		switch(parseInt(sortObject['index'])) {
			case 1:
				content = 'First sorted column: ' + direction;
				break;
			case 2:
				content = 'Second sorted column: ' + direction;
				break;
			default:
				content = 'n-th sorted column: ' + direction;
				break;
		}
		getChild($('#' + id), 1).hover( function(e) {
			DisplayTipBox(e, content);
		}, function() {
			HideTipBox();
		});
	}
	showPreview();
}

function stopSortColumn(tag, count) {
	var id = makeId('sort', tag.split(' ').join('_'), count);
	getChild($('#' + id), 1).html('&nbsp;');
	var index = -1;
	$.each(sortColumnsArray, function(i, column) {
		if (column['name'] == tag) {
			index = i;
			return false;
		}
	});
	sortColumnsArray.splice(index, 1);
	$.each(sortColumnsArray, function(i, column) {
		if (i < index) {
			return true;
		}
		var sortId = makeId('sort', column['name'].split(' ').join('_'), count);
		var val = parseInt(getChild($('#' + sortId), 1).html()) - 1;
		getChild($('#' + sortId), 1).html('' + val);
		var content = null;
		var direction = (column['direction'] == ':asc:') ? 'ascending order' : 'descending order';
		switch(val) {
			case 1:
				content = 'First sorted column: ' + direction;
				break;
			case 2:
				content = 'Second sorted column: ' + direction;
				break;
		}
		if (content != null) {
			getChild($('#' + sortId), 1).hover( function(e) {
				DisplayTipBox(e, content);
			}, function() {
				HideTipBox();
			});
		}
	});
}

function getSortOrder(tag) {
	var ret = null;
	$.each(sortColumnsArray, function(i, column) {
		if (column['name'] == tag) {
			ret = new Object();
			ret['name'] = tag;
			ret['direction'] = column['direction'];
			ret['index'] = '' + (i + 1);
			return false;
		}
	});
	return ret;
}

function addTagToQuery() {
	confirmAddTagDialog.dialog('open');
	$('#customizedViewSelect').val('');
	$('input:radio[name=showAnotherColumn][value=add]').click();
}

function addViewTagsToQuery() {
	confirmAddMultipleTagsDialog.dialog('open');
	$('#selectViews').val('');
	$('input:radio[name=showColumnSet][value=replace]').click();
}

function addViewToListColumns(id) {
	var val = $('#' + id).val();
	if (val == '') {
		alert('Please select an available view.');
		return;
	}
	setViewTags(val);
	var choice = $('input:radio[name=showColumnSet]:checked').val();
	if (choice == 'replace') {
		resultColumns = new Array();
		sortColumnsArray = new Array();
		queryFilter = new Object();
	}
	confirmAddMultipleTagsDialog.dialog('close');
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
	
	var theadRange = $('#Query_Preview_range');
	var trRange = getChild(theadRange, 1);
	var col = getChild(trRange, index + 2);
	col.css('display', 'none');
	
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
		if (tag['name'] == column) {
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
	if (resultColumns.length == 1) {
		var thead = $('#Query_Preview_header');
		var tr1 = thead.find('.sortAndContextMenu');
		var td = getChild(tr1, 2);
		var ul = td.find('ul');
		ul.find('.deleteColumn').css('display', 'none');
	}
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
		select_tags_count = null;
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
	select_tags_count = null;
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
	select_tags_count = null;
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
			td.attr('iRow', '' + i);
			td.attr('tag', tag);
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
				val += item['vals'].join(', ');
				val += item['opUser'] == 'Between' ? ')' : '}';
				break;
				
			}
			td.html(val);
			if (rangeQueryFilter != null && rangeQueryFilter[tag] != null && rangeQueryFilter[tag] == i) {
				td.addClass('rangeConstraint');
			}
			td.click({	td: td },
						function(event) {event.preventDefault(); updateColumnFilter(event.data.td); });
		});
	}
	return divConstraint;
}

function updateColumnFilter(td) {
	var tag = td.attr('tag');
	var index = parseInt(td.attr('iRow'));
	addFilter(tag, index);
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
		var pred = getPredicate(tbody);
		if (pred != null) {
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
			'Cancel': function() {
					$(this).dialog('close');
				},
			'Save': function() {
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

function editTagValues(tag) {
	initDropDownList(tag);
	var div = $('#editTagValuesWrapperDiv');
	div.html('');
	div.css('display', '');
	var tagDiv = editTagValuesTemplate.clone();
	div.append(tagDiv);
	if (confirmTagValuesEditDialog != null) {
		confirmTagValuesEditDialog.remove();
		confirmTagValuesEditDialog = null;
	}
	var table = $('#bulk_edit_table');
	addBulkMultiValueRow(table, tag);
	var width = 0;
	var height = 0;
	for (var i=0; i < tagDiv.children().length; i++) {
		var child = getChild(tagDiv, i+1);
		var crtWidth = child.width();
		if (crtWidth > width) {
			width = crtWidth;
		}
		height += child.height() + 10;
	}
	width += 200;
	height += 200;
	confirmTagValuesEditDialog = tagDiv;
	confirmTagValuesEditDialog.dialog({
		autoOpen: false,
		title: 'Edit values for column "' + tag + '"',
		buttons: {
			'Cancel': function() {
					$(this).dialog('close');
				},
			'Apply': function() {
					applyTagValuesUpdate(tag);
				}
		},
		position: 'top',
		draggable: true,
		height: height,
		modal: false,
		resizable: true,
		width: width,
		beforeClose: function(event, ui) {div.css('display', 'none');}
	});
	confirmTagValuesEditDialog.dialog('open');
}

function addBulkMultiValueRow(table, tag) {
	var tr = $('<tr>');
	table.append(tr);
	var td = $('<td>');
	tr.append(td);
	var id = makeId('multi_valued', ++MULTI_VALUED_ROW_COUNTER);
	tr.attr('id', id);
	td.css('white-space', 'nowrap');
	td.append('Value: ');
	var input = $('<input>');
	input.attr('type', 'text');
	input.attr({	type: 'text' });
	td.append(input);
	if (select_tags[tag] != null && select_tags[tag].length > 0) {
		var select = $('<select>');
		select.change({	to: input,
						from: select },
						function(event) {copyTagValue(event.data.to, event.data.from);});
		td.append(select);
		var option = $('<option>');
		option.text('Choose a value');
		option.attr('value', '');
		select.append(option);
		if (availableTags[tag] == 'timestamptz') {
			input.addClass('datetimepicker');
			bindDateTimePicker();
		} else if (availableTags[tag] == 'date') {
			input.addClass('datepicker');
			bindDatePicker();
		}
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
	}
	if (allTagdefs[tag]['tagdef multivalue']) {
		var imgPlus = $('<img>');
		imgPlus.attr({	src: HOME + '/static/plus.png',
					    width: '16',
					    height: '16',
						alt: '+' });
		imgPlus.click({	table: table,
						tag: tag },
						function(event) {addBulkMultiValueRow(event.data.table, event.data.tag);});
		td.append(imgPlus);
		var img = $('<img>');
		img.attr({	src: HOME + '/static/minus.png',
				    width: '16',
				    height: '16',
					alt: '-' });
		img.click({ id: id },
					function(event) {deleteMultiValueRow(event.data.id);});
		td.append(img);
	}
}

function copyTagValue(to, from) {
	to.val(from.val());
}

function applyTagValuesUpdate(column) {
	var scope = $('input:radio[name=valuesScope]:checked').val();
	if (scope == null) {
		alert('Please check a Scope button.');
		return;
	}
	var action = $('input:radio[name=valuesAction]:checked').val();
	if (action == null) {
		alert('Please check an Action button.');
		return;
	}
	var values = new Array();
	var trs = $('#bulk_edit_table').find('tr');
	$.each(trs, function(i, tr) {
		var td = getChild($(tr), 1);
		var input = getChild(td, 1);
		var value = input.val().replace(/^\s*/, "").replace(/\s*$/, "");
		if (value != '') {
			values.push(value);
		}
	});
	if (action == 'DELETE' && values.length == 0) {
		alert('Please enter a value to be deleted.');
		return;
	}
	values = encodeURIArray(values, '');
	sendBulkRequest(column, scope, action, values);
	confirmTagValuesEditDialog.dialog('close');
}

function deleteTagValues(tag, values) {
	initDropDownList(tag);
	var div = $('#deleteTagValuesWrapperDiv');
	div.html('');
	div.css('display', '');
	var tagDiv = deleteTagValuesTemplate.clone();
	div.append(tagDiv);
	if (confirmTagValuesDeleteDialog != null) {
		confirmTagValuesDeleteDialog.remove();
		confirmTagValuesDeleteDialog = null;
	}
	var tbody = $('#deleteTagValuesTableBody');
	$.each(values, function(i, value) {
		var tr = $('<tr>');
		tbody.append(tr);
		var td = $('<td>');
		tr.append(td);
		var input = $('<input>');
		input.attr('type', 'checkbox');
		td.append(input);
		td = $('<td>');
		tr.append(td);
		td.html(value);
	});
	
	var width = 0;
	var height = 0;
	for (var i=0; i < tagDiv.children().length; i++) {
		var child = getChild(tagDiv, i+1);
		var crtWidth = child.width();
		if (crtWidth > width) {
			width = crtWidth;
		}
		height += child.height() + 10;
	}
	width += 100;
	height += 200;
	confirmTagValuesDeleteDialog = tagDiv;
	confirmTagValuesDeleteDialog.dialog({
		autoOpen: false,
		title: 'Delete values for column "' + tag + '"',
		buttons: {
			'Cancel': function() {
					$(this).dialog('close');
				},
			'Apply': function() {
					applyTagValuesDelete(tag);
				}
		},
		position: 'top',
		draggable: true,
		height: height,
		modal: false,
		resizable: true,
		width: width,
		beforeClose: function(event, ui) {div.css('display', 'none');}
	});
	confirmTagValuesDeleteDialog.dialog('open');
}

function applyTagValuesDelete(column) {
	var scope = $('input:radio[name=deleteValuesScope]:checked').val();
	if (scope == null) {
		alert('Please check a Scope button.');
		return;
	}
	var tbody = $('#deleteTagValuesTableBody');
	var values = new Array();
	$.each(tbody.children(), function(i, tr) {
		var td = getChild($(tr), 1);
		var check = getChild(td, 1);
		if (check.prop('checked')) {
			values.push(encodeSafeURIComponent(getChild($(tr), 2).html()));
		}
	});
	if (values.length == 0) {
		alert('Please check the values to be deleted.');
		return;
	}
	sendBulkRequest(column, scope, 'DELETE', values);
	confirmTagValuesDeleteDialog.dialog('close');
}

function sendBulkRequest(column, scope, action, values) {
	editBulkInProgress = true;
	var value = values.join(',');
	if (scope == 'filter') {
		var predUrl = HOME + '/tags/' + getQueryPredUrl('');
		var url = predUrl + '(' + encodeSafeURIComponent(column) + '=' + value + ')';
		$.ajax({
			url: url,
			type: action,
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: true,
			success: function(data, textStatus, jqXHR) {
				showPreview();
				editBulkInProgress = false;
			},
			error: function(jqXHR, textStatus, errorThrown) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
			}
		});
	} else {
		// update each row from the page
		var tbody = $('#Query_Preview_tbody');
		
		// get the rows ids
		var ids = new Array();
		$.each(tbody.children(), function(i, tr) {
			if ($(tr).css('display') == 'none') {
				return false;
			} else {
				ids.push(encodeSafeURIComponent($(tr).attr('recordId')));
			}
		});
		
		// sent the request
		var id = ids.join(',');
		var predUrl = HOME + '/tags/id=' + id;
		var url = predUrl + '(' + encodeSafeURIComponent(column) + '=' + value + ')';
		$.ajax({
			url: url,
			type: action,
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: true,
			success: function(data, textStatus, jqXHR) {
				showPreview();
				editBulkInProgress = false;
			},
			error: function(jqXHR, textStatus, errorThrown) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
			}
		});
	}
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
	if (utcValues.length == 1) {
		utcValues.push('00');
	}
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
			'Log out now': function() {
					runLogoutRequest();
					$(this).dialog('close');
				},
			'Extend session': function() {
					runExtendRequest();
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

function getSelectRange(totalRows) {
	var select = $('#resultsRange').find('select');
	if (select.get(0) == null) {
		$('#resultsRange').html('');
		select = $('<select>');
		select.attr('id', 'showResultRange');
		select.change(function(event) {accessNextPage();});
		$('#resultsRange').append(select);
	}
	var totalPages = Math.ceil(totalRows / PREVIEW_LIMIT);
	var minPage = PAGE_PREVIEW - 9;
	var maxPage = PAGE_PREVIEW + 11;
	if (minPage < 0) {
		minPage = 0;
		maxPage = 20;
		if (maxPage > totalPages) {
			maxPage = totalPages;
		}
	} else if (maxPage > totalPages) {
		maxPage = totalPages;
		minPage = maxPage - 20;
		if (minPage < 0) {
			minPage = 0;
		}
	}
	var options = select.children().length;
	var entries = maxPage - minPage;
	if (minPage > 0) {
		entries++;
	}
	if (maxPage < totalPages) {
		entries++;
	}
	if (options < entries) {
		var delta = entries - options;
		for (var i=0; i < delta; i++) {
			select.append($('<option>'));
		}
	}
	var index = 0;
	for (var i=0; i < entries; i++) {
		var option = getChild(select, i+1);
		option.css('display', '');
		if (i == 0 && minPage > 0) {
			option.text('1 to ' + PREVIEW_LIMIT);
			option.attr('value', '0');
		} else if (i == (entries - 1) && maxPage < totalPages) {
			option.text('' + ((totalPages - 1) * PREVIEW_LIMIT  + 1) + ' to ' + totalRows);
			option.attr('value', '' + (totalPages - 1));
		} else {
			var maxVal = (minPage + index + 1) * PREVIEW_LIMIT;
			if (maxVal > totalRows) {
				maxVal = totalRows;
			}
			option.text('' + ((minPage + index) * PREVIEW_LIMIT + 1) + ' to ' + maxVal);
			option.attr('value', '' + (minPage + index));
			index++;
		}
	}
	options = select.children().length;
	for (var i = entries; i < options; i++) {
		getChild(select, i+1).css('display', 'none');
	}
	select.val('' + PAGE_PREVIEW);
}

function editCell(td, column, id) {
	if (clickedCancelOK) {
		// we are in the case when a click Cancel or OK button has propagated to the td
		// so ignore this event
		clickedCancelOK = false;
		return;
	}
	if (editCellInProgress) {
		return;
	}
	editCellInProgress = true;
	var origValue = td.html();
	var table = null;
	var input = null;
	var select = null;
	td.html('');
	td.css('white-space', 'nowrap');
	if (allTagdefs[column]['tagdef multivalue']) {
		table = $('<table>');
		td.append(table);
		var values = origValue.split('<br>');
		if (values.length == 0) {
			values.push('');
		}
		$.each(values, function(i, value) {
			addMultiValueRow(table, column, value);
		});
	} else if (availableTags[column] == 'boolean') {
		select = $('<select>');
		var option = $('<option>');
		option.text('false');
		option.attr('value', 'false');
		select.append(option);
		option = $('<option>');
		option.text('true');
		option.attr('value', 'true');
		select.append(option);
		select.val(origValue);
		td.append(select);
	}
	else if (availableTags[column] == 'empty') {
		select = $('<select>');
		var option = $('<option>');
		option.text('Tag absent');
		option.attr('value', 'not set');
		select.append(option);
		option = $('<option>');
		option.text('Tagged');
		option.attr('value', 'is set');
		select.append(option);
		select.val(origValue);
		td.append(select);
	} else {
		input = $('<input>');
		input.attr('type', 'text');
		td.append(input);
		input.val(origValue);
	}
	var button = $('<input>');
	button.attr('type', 'button');
	button.val('Delete');
	td.append(button);
	button.click({	origValue: origValue,
					td: td,
					id: id,
					column: column },
					function(event) {deleteCell(event.data.td, event.data.origValue, event.data.column, event.data.id);});
	button = $('<input>');
	button.attr('type', 'button');
	button.val('Cancel');
	td.append(button);
	button.click({	origValue: origValue,
					td: td },
					function(event) {clickedCancelOK = true; editCellInProgress = false; event.data.td.html(event.data.origValue); event.data.td.css('white-space', 'normal');});
	if (availableTags[column] == 'timestamptz' || availableTags[column] == 'date' || allTagdefs[column]['tagdef multivalue'] || select != null) {
		var button = $('<input>');
		button.attr('type', 'button');
		button.val('OK');
		td.append(button);
		button.click({	td: td,
						input: input,
						origValue: origValue,
						column: column,
						id: id },
						function(event) {clickedCancelOK = true; updateCell(event.data.td, event.data.origValue, event.data.column, event.data.id);});
	}
	if (select != null) {
		select.focus();
	} else if (!allTagdefs[column]['tagdef multivalue']) {
		if (availableTags[column] == 'timestamptz') {
			input.addClass('datetimepicker');
			bindDateTimePicker();
		} else if (availableTags[column] == 'date') {
			input.addClass('datepicker');
			bindDatePicker();
		} else {
			input.keypress({input: input,
							origValue: origValue,
							td: td ,
							column: column,
							id: id },
							function(event) {if (event.which == 13) updateCell(event.data.td, event.data.origValue, event.data.column, event.data.id);});
		}
		input.focus();
	} else {
		table.focus();
	}
}

function updateCell(td, origValue, column, id) {
	editCellInProgress = false;
	var child = getChild(td, 1);
	td.css('white-space', 'normal');
	var value = null;
	var tagAbsent = false;
	var values = new Array();
	if (child.is('SELECT')) {
		value = child.val();
		if (availableTags[column] == 'empty') {
			if (value == 'is set') {
				values.push(ops['Tagged']); 
			} else {
				tagAbsent = true;
			}
		} else if (availableTags[column] == 'boolean') {
			values.push(value); 
		}
	} else if (child.is('INPUT')) {
		value = child.val().replace(/^\s*/, "").replace(/\s*$/, "");
		if (value != '') {
			values.push(value); 
		}
	} else if (child.is('TABLE')) {
		var trs = child.find('tr');
		$.each(trs, function(i, tr) {
			var td = getChild($(tr), 1);
			var crtVal = getChild(td, 1).val().replace(/^\s*/, "").replace(/\s*$/, "");
			if (crtVal != '') {
				values.push(crtVal); 
			}
		});
		value = values.join('<br>');
	}
	td.html(value);
	if (value != origValue) {
		if (value != '') {
			if (child.is('TABLE') && origValue != '' || tagAbsent) {
				// delete all old values
				var url = HOME + '/tags/id=' + encodeSafeURIComponent(id) + '(' + encodeSafeURIComponent(column) + ')';
				$.ajax({
					url: url,
					type: 'DELETE',
					headers: {'User-agent': 'Tagfiler/1.0'},
					async: true,
					success: function(data, textStatus, jqXHR) {
						if (!tagAbsent) {
							modifyCell(td, origValue, column, id, value, values);
						}
					},
					error: function(jqXHR, textStatus, errorThrown) {
						handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
					}
				});
			} else {
				modifyCell(td, origValue, column, id, value, values);
			}
		} else {
			modifyCell(td, origValue, column, id, value, values);
		}
	}
}

function modifyCell(td, origValue, column, id, newValue, values) {
	if (newValue != '') {
		// update value
		var value = encodeURIArray(values, '').join(',');
		var url = HOME + '/tags/id=' + encodeSafeURIComponent(id) + '(' + encodeSafeURIComponent(column) + '=' + value + ')';
		$.ajax({
			url: url,
			type: 'PUT',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: true,
			success: function(data, textStatus, jqXHR) {
			},
			error: function(jqXHR, textStatus, errorThrown) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
				td.html(origValue);
			}
		});
	} else {
		// delete value(s)
		var url = HOME + '/tags/id=' + encodeSafeURIComponent(id) + '(' + encodeSafeURIComponent(column) + ')';
		$.ajax({
			url: url,
			type: 'DELETE',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: true,
			success: function(data, textStatus, jqXHR) {
			},
			error: function(jqXHR, textStatus, errorThrown) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
			}
		});
	}
	if (origValue.length == 0) {
		td.removeClass('tablecelledit');
		td.contextMenu({ menu: 'tablecellMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
	} else if (newValue.length == 0) {
		td.addClass('tablecelledit');
		td.contextMenu({ menu: 'tablecellEditMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
	}
}

function deleteCell(td, origValue, column, id) {
	// delete value(s)
	var url = HOME + '/tags/id=' + encodeSafeURIComponent(id) + '(' + encodeSafeURIComponent(column) + ')';
	$.ajax({
		url: url,
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		success: function(data, textStatus, jqXHR) {
			clickedCancelOK = true;
			editCellInProgress = false;
			td.html('');
			td.css('white-space', 'normal');
			td.addClass('tablecelledit');
			td.contextMenu({ menu: 'tablecellEditMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

function enableEdit() {
	enabledEdit = true;
	$('#enableEdit').css('display', 'none');
	$('#disableEdit').css('display', '');
	$('.tablecell').unbind('click');
	var tbody = $('#Query_Preview_tbody');
	$.each(tbody.children(), function(i, tr) {
		if ($(tr).css('display') == 'none') {
			return false;
		}
		var id = $(tr).attr('recordId');
		$.each(resultColumns, function(j, column) {
			var td = getChild($(tr), j+2);
			td.click({	td: td,
						column: column,
						id:  id },
						function(event) {editCell(event.data.td, event.data.column, event.data.id);});
		});
	});
	$('.tablecell').contextMenu({ menu: 'tablecellMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
	$('.tablecelledit').contextMenu({ menu: 'tablecellEditMenu' }, function(action, el, pos) { contextMenuWork(action, el, pos); });
	$('#GlobalMenu').slideUp('slow');
}

function disableEdit() {
	enabledEdit = false;
	$('#disableEdit').css('display', 'none');
	$('#enableEdit').css('display', '');
	$('.tablecell').unbind();
	$('#GlobalMenu').slideUp('slow');
	$('.tablecell').click(function(event) {DisplayTipBox(event, 'You might "Enable edit" via the "Actions" menu.');});
	$('.tablecell').mouseout(function(event) {HideTipBox();});
}

function bindDateTimePicker() {
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
}

function bindDatePicker() {
	$('.datepicker').datetimepicker({	dateFormat: 'yy-mm-dd',
										timeFormat: '',
										separator: '',
										changeYear: true,
										showTime: false,
										showHour: false,
										showMinute: false
	});
}

function contextMenuWork(action, el, pos) {
	switch (action) {
	case 'delete':
		var id = el.parent().attr('recordId');
		var value = el.html();
		var column = el.attr('tag');
		var predUrl = HOME + '/tags/id=' + encodeSafeURIComponent(id);
		var url = predUrl + '(' + encodeSafeURIComponent(column) + ')';
		$.ajax({
			url: url,
			type: 'DELETE',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: true,
			success: function(data, textStatus, jqXHR) {
				// force a preview 'refresh'
				editBulkInProgress = true;
				showPreview();
				editBulkInProgress = false;
			},
			error: function(jqXHR, textStatus, errorThrown) {
				handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
			}
		});
		break;
	case 'bulkdelete':
		var tag = el.attr('tag');
		var values = el.html().split('<br>');
		deleteTagValues(tag, values);
		break;
	case 'edit':
		el.click();
		break;
	}
}

function contextRangeWork(action, el) {
	var tag = el.attr('tag');
	el.find('.range').removeClass('range');
	switch (action) {
	case 'apply':
		break;
	case 'clear':
		var last = queryFilter[tag].length - 1;
		queryFilter[tag].splice(last, 1);
		if (queryFilter[tag].length == 0) {
			delete queryFilter[tag];
		}
		break;
	}
	var iCol = parseInt(el.attr('iCol'));
	var thead = $('#Query_Preview_header');
	var tr3 = thead.find('.columnFilter');
	var td3 = getChild(tr3, iCol+2);
	td3.find('.rangeConstraint').removeClass('rangeConstraint');
	delete saveQueryFilter[tag];
	delete rangeQueryFilter[tag];
	updateRangeFilterInProgress();
	showPreview();
}

function showRange() {
	displayRangeValues = true;
	$('#Query_Preview_range').css('display', '');
	var trRange = getChild($('#Query_Preview_range'), 1);
	var trBody = getChild($('#Query_Preview_tbody'), 1);
	$.each(resultColumns, function(i, column) {
		var tdRange = getChild(trRange, i+2);
		var tdBody = getChild(trBody, i+2);
		tdRange.attr('width', tdBody.width() + 'px');
	});
	$('#showRange').css('display', 'none');
	$('#hideRange').css('display', '');
	if (lastSaveQueryFilter == null) {
		loadRange(null);
		saveQueryFilter = new Object();
		rangeQueryFilter = new Object();
		enableRangeEvents();
	} else {
		saveQueryFilter = lastSaveQueryFilter;
		rangeQueryFilter = lastRangeQueryFilter;
		// force refresh
		editBulkInProgress = true;
		showPreview();
		editBulkInProgress = false;
	}
}

function hideRange() {
	$('.range').removeClass('range');
	$('.rangeHeader').removeAttr('firstClicked');
	$('.rangeHeader').unbind('mouseenter mouseleave');
	displayRangeValues = false;
	lastSaveQueryFilter = saveQueryFilter;
	lastRangeQueryFilter = rangeQueryFilter;
	saveQueryFilter = null;
	rangeQueryFilter = null;
	$('#Query_Preview_range').css('display', 'none');
	$('#showRange').css('display', '');
	$('#hideRange').css('display', 'none');
	$('.rangeConstraint').removeClass('rangeConstraint');
}

function deleteMultiValueRow(id) {
	$('#' + id).remove();
}

function addMultiValueRow(table, tag, value) {
	var tr = $('<tr>');
	var id = makeId('multi_valued', ++MULTI_VALUED_ROW_COUNTER);
	tr.attr('id', id);
	table.append(tr);
	var td = $('<td>');
	td.css('white-space', 'nowrap');
	tr.append(td);
	var input = $('<input>');
	if (availableTags[tag] == 'timestamptz') {
		input.addClass('datetimepicker');
		bindDateTimePicker();
	} else if (availableTags[tag] == 'date') {
		input.addClass('datepicker');
		bindDatePicker();
	}
	input.attr('type', 'text');
	td.append(input);
	input.val(value);
	var imgPlus = $('<img>');
	imgPlus.attr({	src: HOME + '/static/plus.png',
				    width: '16',
				    height: '16',
					alt: '+' });
	imgPlus.click({	table: table,
					tag: tag },
					function(event) {addMultiValueRow(event.data.table, event.data.tag, '');});
	td.append(imgPlus);
	var img = $('<img>');
	img.attr({	src: HOME + '/static/minus.png',
			    width: '16',
			    height: '16',
				alt: '-' });
	img.click({ id: id },
				function(event) {deleteMultiValueRow(event.data.id);});
	td.append(img);
}

function rangeFilter(event, td) {
	var selected = td.hasClass('range');
	var isCtrl = event.ctrlKey;
	var isShift = event.shiftKey;
	var tag = td.attr('tag');
	var tdRange = td.parent().parent().parent().parent().parent();
	if ((isShift || !isCtrl)  && rangeQueryFilter[tag] != null) {
		contextRangeWork('clear', tdRange);
	}
	if (selected && !isCtrl && !isShift) {
		tdRange.removeAttr('firstClicked');
		return;
	}
	tdRange.attr('rangeClicked', true);
	if (columnRangeValues[tag] == null) {
		columnRangeValues[tag] = headerRangeValues[tag];
	}
	if (saveQueryFilter[tag] == null) {
		// first click
		if (queryFilter[tag] != null) {
			saveQueryFilter[tag] = queryFilter[tag];
		} else {
			saveQueryFilter[tag] = new Array();
			queryFilter[tag] = new Array();
		}
		rangeQueryFilter[tag] = saveQueryFilter[tag].length;
		var pred = new Object();
		pred['op'] = '=';
		pred['vals'] = [];
		pred['opUser'] = 'Equal';
		queryFilter[tag].push(pred);
		if (tdRange.attr('firstClicked') == null) {
			tdRange.attr('firstClicked', td.attr('iRow'));
		}
	}
	if (isShift && tdRange.attr('firstClicked') != null) {
		var first = parseInt(tdRange.attr('firstClicked'));
		var row = parseInt(td.attr('iRow'));
		if (first > row) {
			var temp = row;
			row = first;
			first = temp;
		}
		var tbody = td.parent().parent();
		for (var i=first; i <= row; i++) {
			var tr = getChild(tbody, i+1);
			var crtTd = getChild(tr, 1);
			var originalValue = crtTd.attr('originalValue');
			crtTd.addClass('range');
			var last = queryFilter[tag].length - 1;
			queryFilter[tag][last]['vals'].push(originalValue);
		}
	} else {
		var originalValue = td.attr('originalValue');
		if (td.hasClass('range')) {
			td.removeClass('range');
			// remove the value from the filter
			var last = queryFilter[tag].length - 1;
			var values = queryFilter[tag][last]['vals'];
			var index = -1;
			$.each(values, function(i, value) {
				if (value == originalValue) {
					index = i;
					return false;
				}
			});
			values.splice(index, 1);
			if (values.length == 0) {
				queryFilter[tag].splice(last, 1);
				if (queryFilter[tag].length == 0) {
					delete queryFilter[tag];
				}
				delete saveQueryFilter[tag];
				delete rangeQueryFilter[tag];
				tdRange.unbind('mouseenter mouseleave');
				updateRangeFilterInProgress();
			}
		} else {
			td.addClass('range');
			var last = queryFilter[tag].length - 1;
			queryFilter[tag][last]['vals'].push(originalValue);
		}
	}
	showPreview();
}

function updateRangeFilterInProgress() {
	$('#clearAllFilters').css('display', queryHasFilters() ? '' : 'none');
}

function cleanupRangeFilter() {
	$.each(saveQueryFilter, function(tag, value) {
		var last = queryFilter[tag].length - 1;
		queryFilter[tag].splice(last, 1);
		if (queryFilter[tag].length == 0) {
			delete queryFilter[tag];
		}
	});
	$('.rangeHeader').unbind('mouseenter mouseleave');
	saveQueryFilter = null;
	rangeQueryFilter = null;
	showPreview();
}

function addFilter(tag, predIndex) {
	$('.editColumnFilter').css('display', 'none');
	$('.addFilter').css('display', 'none');
	savePredicateFilter = (predIndex != -1) ? queryFilter[tag][predIndex] : null;
	initDropDownList(tag);
	var index = -1;
	$.each(resultColumns, function(i, column) {
		if (column == tag) {
			index = i;
			return false;
		}
	});
	var filterIndex = predIndex;
	if (predIndex == -1) {
		if (queryFilter[tag] == null) {
			queryFilter[tag] = new Array();
		}
		filterIndex = queryFilter[tag].length;
	}
	var thead = $('#Query_Preview_header');
	var tr3 = thead.find('.columnFilter');
	var td3 = getChild(tr3, index+2);
	var divConstraint = getChild(td3, 1);
	predicateTable = $('<table>');
	predicateTable.attr('tag', tag);
	predicateTable.attr('filterIndex', filterIndex);
	var fieldset = $('<fieldset>');
	fieldset.addClass('rangeConstraint');
	fieldset.append(predicateTable);
	if (predIndex == -1) {
		divConstraint.append(fieldset);
	} else {
		var div = getChild(divConstraint, 1);
		var table = getChild(div, 1);
		var tbody = getChild(table, 1);
		var tr = getChild(tbody, predIndex+1);
		var td = getChild(tr, 1);
		var newTd = $('<td>');
		tr.append(newTd);
		newTd.append(fieldset);
		newTd.insertAfter(td);
		td.remove();
	}
	var id = makeId('row', ++ROW_COUNTER);
	var tr = $('<tr>');
	tr.attr('id', id);
	predicateTable.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.css('padding', '0px 0px 0px 0px');
	td.attr('valign', 'top');
	var select = getSelectTagOperator(tag, availableTags[tag]);
	var selId = select.attr('id');
	td.append(select);
	if (predIndex != -1) {
		var op = savePredicateFilter['opUser'];
		select.val(op);
	}
	td = $('<td>');
	td.css('padding', '0px 0px 0px 0px');
	tr.append(td);
	var tableId = makeId('table', ROW_COUNTER);
	if (availableTags[tag] != 'empty') {
		var table = $('<table>');
		table.attr('id', tableId);
		td.append(table);
		var tdTable = $('<td>');
		tdTable.css('text-align', 'center');
		tdTable.css('margin-top', '0px');
		tdTable.css('margin-bottom', '0px');
		tdTable.css('padding', '0px 0px 0px 0px');
		tr.append(tdTable);
		addNewValue(ROW_COUNTER, availableTags[tag], selId, tag, null);
		if ($('#' + selId).val() == 'Between') {
			tdTable.css('display', 'none');
		} else if ($('#' + selId).val() == 'Tag absent') {
			td.css('display', 'none');
		}
	}
	if (predIndex != -1) {
		var values = savePredicateFilter['vals'];
		var table = $('#' + tableId);
		var tbody = getChild(table, 1);
		$.each(values, function(i, value) {
			if (i > 0) {
				addNewValue(ROW_COUNTER, availableTags[tag], selId, tag, null);
			}
			var tr = getChild(tbody, i+1);
			var td = getChild(tr, 1);
			var input = getChild(td, 1);
			input.val(value);
		});
	}
	var buttonTable = $('<table>');
	buttonTable.css('float', 'right');
	fieldset.append(buttonTable);
	tr = $('<tr>');
	buttonTable.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.css('padding', '0px 0px 0px 0px');
	td.css('text-align', 'right');
	var button = $('<input>');
	button.attr('type', 'button');
	button.val('Cancel');
	td.append(button);
	button.click(function(event) {cancelPredicate();});
	button = $('<input>');
	button.attr('type', 'button');
	button.val('OK');
	button.click(function(event) {savePredicate();});
	td.append(button);
}

function cancelPredicate() {
	$('.editColumnFilter').css('display', '');
	$('.addFilter').css('display', '');
	var tag = predicateTable.attr('tag');
	var index = parseInt(predicateTable.attr('filterIndex'));
	if (savePredicateFilter == null) {
		if (queryFilter[tag].length > index) {
			queryFilter[tag].splice(index, 1);
		}
		if (queryFilter[tag].length == 0) {
			delete queryFilter[tag];
		}
	} else {
		queryFilter[tag][index] = savePredicateFilter;
	}
	predicateTable = null;
	// force a preview 'refresh'
	editBulkInProgress = true;
	showPreview();
	editBulkInProgress = false;
}

function savePredicate() {
	$('.editColumnFilter').css('display', '');
	$('.addFilter').css('display', '');
	var tag = predicateTable.attr('tag');
	var index = parseInt(predicateTable.attr('filterIndex'));
	updateTagPredicate();
	var pred = queryFilter[tag][index];
	if (pred['opUser'] == 'None') {
		if (queryFilter[tag].length > index) {
			queryFilter[tag].splice(index, 1);
		}
		if (queryFilter[tag].length == 0) {
			delete queryFilter[tag];
		}
	}
	predicateTable = null;
	// force a preview 'refresh'
	editBulkInProgress = true;
	showPreview();
	editBulkInProgress = false;
}

function updateTagPredicate() {
	var tag = predicateTable.attr('tag');
	var index = parseInt(predicateTable.attr('filterIndex'));
	var tbody = getChild(predicateTable, 1);
	var pred = getPredicate(tbody);
	if (pred == null) {
		pred = new Object();
		pred['opUser'] = 'None';
	}
	queryFilter[tag][index] = pred;
}

function getPredicate(tbody) {
	var pred = null;
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
			pred = new Object();
			pred['opUser'] = op;
			pred['vals'] = new Array();
			pred['vals'].push(val1);
			pred['vals'].push(val2);
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
			pred = new Object();
			pred['opUser'] = op;
			pred['op'] = ops[op];
			pred['vals'] = values;
		}
	} else if (op == 'Tagged') {
		pred = new Object();
		pred['opUser'] = op;
		pred['vals'] = new Array();
	} else {
		pred = new Object();
		pred['opUser'] = op;
		pred['op'] = ops[op];
		pred['vals'] = new Array();
	}
	return pred;
}

function enableRangeEvents() {
	$('.rangeHeader').hover(function(event) {setColumnRange(event, $(this));},
							function(event) {resetColumnRange(event, $(this));});
}

function setColumnRange(event, tdRange) {
	tdRange.addClass('rangehover');
	var tag = tdRange.attr('tag');
	if (columnRangeValues[tag] == null) {
		loadRange(tdRange);
	} else {
		var div1 = getChild(tdRange, 1);
		var div2 = getChild(tdRange, 2);
		div1.css('display', 'none');
		div2.css('display', '');
	}
}

function resetColumnRange(event, tdRange) {
	tdRange.removeClass('rangehover');
	var tag = tdRange.attr('tag');
	var div1 = getChild(tdRange, 1);
	var div2 = getChild(tdRange, 2);
	div1.css('display', '');
	div2.css('display', 'none');
}

var policies = {'anonymous': 'anyone', 
		'subject': 'only clients who can access subject', 
		'subjectowner': 'only owner of subject', 
		'tag': 'only clients in tagdef ACL', 
		'tagorsubject': 'only clients who can access subject or who are in tagdef ACL', 
		'tagandsubject': 'only clients who can access subject who is also in tagdef ACL', 
		'tagorowner': 'only owner of subjects or who is in tagdef ACL', 
		'tagandowner': 'only owner of subject who is also in tagdef ACL',
		"system" : "no access"
};

var tagdefPolicies = {'anonymous': 'Any client may access', 
		'subject': 'Subject authorization is observed', 
		'subjectowner': 'Subject owner may access', 
		'tag': 'Tag authorization is observed', 
		'tagorsubject': 'Tag or subject authorization is sufficient', 
		'tagandsubject': 'Tag and subject authorization are required', 
		'tagorowner': 'Tag authorization or subject ownership is sufficient', 
		'tagandowner': 'Tag authorization and subject ownership is required',
		"system" : "No client can access"
};

var tagPolicies = ['anonymous', 'subject', 'subjectowner', 'tag', 'tagorsubject', 'tagandsubject'];
var tagdefsColumns = ['tagdef', 
                      'tagdef type', 
                      'tagdef multivalue', 
                      'tagdef unique', 
                      'owner',
                      'tagdef readpolicy',
                      'tagdef writepolicy'];

var browsersImmutableTags = [ 'check point offset', 'key', 'sha256sum' ];

var SESSIONID;
var USER_ROLES;
var HELP_URL;
var BUGS_URL;

function initUI(home, user, webauthnhome, uiopts, count) {
	//alert(uiopts);
	if (count == null) {
		count = 0;
	}
	HOME = home;
	USER = user;
	WEBAUTHNHOME = webauthnhome;
	// convert to JSON
	uiopts = $.parseJSON(uiopts);
	HELP_URL = uiopts.help;
	BUGS_URL = uiopts.bugs;
	var api = uiopts.api;
	var isLogin = false;
	if (api.length > 0) {
		if (api[0] == 'tagdef') {
			var url = HOME + '/session'
			$.ajax({
				url: url,
				accepts: {text: 'application/json'},
				dataType: 'json',
				headers: {'User-agent': 'Tagfiler/1.0'},
				async: true,
		  		timeout: AJAX_TIMEOUT,
				success: function(data, textStatus, jqXHR) {
					if (api[0] == 'tagdef') {
						manageTagDefinitions(data.roles);
					}
				},
				error: function(jqXHR, textStatus, errorThrown) {
					var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
					if (retry && count <= MAX_RETRIES) {
						var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
						setTimeout(function(){initUI(home, user, webauthnhome, uiopts, count)}, delay);
					}
				}
			});
		} else if (api[0] == 'login') {
			renderLogin();
			isLogin = true;
		} else if (api[0] == 'query') {
			getTopPage(uiopts, 'query');
		} else if (api[0] == 'tags') {
			getTopPage(uiopts, 'tags');
		} else if (api[0] == 'home') {
			getRoles();
		}
	} else {
		getTopPage(uiopts, null);
	}
	initIdleWarning();
	runSessionPolling(uiopts.pollmins, 2*uiopts.pollmins);
	if (!isLogin) {
		startCookieTimer(1000);
	}
}

function renderLogin() {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Log In');
	var fieldset = $('<fieldset>');
	uiDiv.append(fieldset);
	var legend = $('<legend>');
	fieldset.append(legend);
	legend.html('Login');
	var table = $('<table>');
	fieldset.append(table);
	var tr = $('<tr>');
	table.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.html('Username: ');
	var input = $('<input>');
	input.attr({'type': 'text',
		'id': 'username',
		'name': 'username',
		'size': 15
	});
	td.append(input);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.html('Password: ');
	var input = $('<input>');
	input.attr({'type': 'password',
		'id': 'password',
		'name': 'password',
		'size': 15
	});
	td.append(input);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	var input = $('<input>');
	input.attr({'type': 'button',
		'value': 'Login'
	});
	input.val('Login');
	td.append(input);
	input.click(function(event) {submitLogin();});
	td.append(input);
}

function submitLogin(count) {
	if (count == null) {
		count = 0;
	}
	var user = $('#username').val();
	var password = $('#password').val();
	var url = HOME + '/session';
	var obj = new Object();
	obj['username'] = user;
	obj['password'] = password;
	document.body.style.cursor = "wait";
	$.ajax({
		url: url,
		type: 'POST',
		data: obj,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			document.body.style.cursor = "default";
			window.location = window.location;
		},
		error: function(jqXHR, textStatus, errorThrown) {
			document.body.style.cursor = "default";
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){submitLogin(count)}, delay);
			}
		}
	});
}

function getRoles(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/session';
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			USER_ROLES = data['attributes'];
			USER = data['client'];
			showAuthnInfo(data);
			showTopMenu();
			homePage();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){getRoles(count)}, delay);
			}
		}
	});
}

function getTopPage(uiopts, page, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/session';
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			USER_ROLES = data['attributes'];
			USER = data['client'];
			showAuthnInfo(data);
			showTopMenu();
			if (page == 'query') {
				queryPage(uiopts);
			} else if (page == 'tags') {
				tagsUI(uiopts['queryopts']['url'], null, USER_ROLES);
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){getTopPage(uiopts, count)}, delay);
			}
		}
	});
}

function queryPage(uiopts) {
	renderQueryHTML();
	initPSOC(HOME, USER, WEBAUTHNHOME, uiopts.path, uiopts.queryopts);
}

function showAuthnInfo(data) {
	var since = getLocaleTimestamp(data['since']);
	since = since.split(" ")[1].split('.')[0];
	var expires = getLocaleTimestamp(data['expires']);
	expires = expires.split(" ")[1].split('.')[0];
	
	var td = $('#authninfo');
	td.html('');
	var table = $('<table>');
	td.append(table);
	table.addClass('authninfo');
	var tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.html('User:');
	td = $('<td>');
	tr.append(td);
	var a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:userInfo()'});
	a.html(USER);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:userLogout()'});
	a.html('log out');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:userChangePassword()'});
	a.html('change password');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.html('Since:');
	td = $('<td>');
	tr.append(td);
	var span = $('<span>');
	td.append(span);
	span.attr({'id': 'sincetime'});
	span.html(since);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.html('Expires:');
	td = $('<td>');
	tr.append(td);
	span = $('<span>');
	td.append(span);
	span.attr({'id': 'untiltime'});
	span.html(expires);
}

function showTopMenu() {
	var tr = $('#topmenu');
	tr.html('');
	var td = $('<td>');
	tr.append(td);
	var a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:homePage()'});
	a.html('Home');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:manageUsers()'});
	a.html('Manage users');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:manageAttributes()'});
	a.html('Manage attributes');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:uploadStudy()'});
	a.html('Upload study');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:downloadStudy("study?action=download")'});
	a.html('Download study');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': 'javascript:queryByTags()'});
	a.html('Query by tags');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': HELP_URL});
	a.html('Help');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': BUGS_URL});
	a.html('Bugs');
	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': HOME + '/log'});
	a.html('Logs');
}

function manageTagDefinitions(roles, count) {
	if (count == null) {
		count = 0;
	}
	var uiDiv = $('#ui');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Tag definitions');
	h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('User');
	
	// build the table for the user tags
	var table = $('<table>');
	uiDiv.append(table);
	table.addClass('tagdefs');
	table.attr('id', 'User_tagdefs');
	
	// build the header
	var tr = $('<tr>');
	table.append(tr);
	tr.addClass('heading');
	tr.attr('id', 'tr_0');
	var th = $('<th>');
	tr.append(th);
	th.attr('name', 'tagname');
	th.html('Tag name');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'typestr');
	th.html('Tag type');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'multivalue');
	th.html('# Values');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'owner');
	th.html('Owner');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'readpolicy');
	th.html('Tag readers');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'writepolicy');
	th.html('Tag writers');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'unique');
	th.html('Tag unique');
	
	tr = $('<tr>');
	tr.attr('id', 'tr_1');
	table.append(tr);
	tr.addClass('tagdefcreate');
	var td = $('<td>');
	tr.append(td);
	var input = $('<input>');
	input.attr({'type': 'text',
		'name': 'tag-1',
		'id': 'tag-1'});
	td.append(input);
	td = $('<td>');
	tr.append(td);
	var select = $('<select>');
	td.append(select);
	select.attr({'name': 'type-1',
		'id': 'type-1',
		'onclick': "chooseTypedefs('"+HOME+"', 'type-1')"});
	var option = $('<option>');
	option.text('No content');
	option.attr('value', 'empty');
	select.append(option);
	td = $('<td>');
	tr.append(td);
	select = $('<select>');
	td.append(select);
	select.attr({'name': 'multivalue-1',
		'id': 'multivalue-1'});
	option = $('<option>');
	option.text('0 or 1');
	option.attr('value', 'false');
	select.append(option);
	option = $('<option>');
	option.text('0 or more');
	option.attr('value', 'true');
	select.append(option);
	td = $('<td>');
	tr.append(td);
	td.html('N/A');
	td = $('<td>');
	tr.append(td);
	select = $('<select>');
	td.append(select);
	select.attr({'name': 'readpolicy-1',
		'id': 'readpolicy-1'});
	$.each(tagPolicies, function(i, key) {
		option = $('<option>');
		option.text(policies[key]);
		option.attr('value', key);
		select.append(option);
	});
	td = $('<td>');
	tr.append(td);
	select = $('<select>');
	td.append(select);
	select.attr({'name': 'writepolicy-1',
		'id': 'writepolicy-1'});
	$.each(tagPolicies, function(i, key) {
		option = $('<option>');
		option.text(policies[key]);
		option.attr('value', key);
		select.append(option);
	});
	td = $('<td>');
	tr.append(td);
	select = $('<select>');
	td.append(select);
	select.attr({'name': 'unique-1',
		'id': 'unique-1'});
	option.text('False');
	option.attr('value', 'false');
	select.append(option);
	option = $('<option>');
	option.text('True');
	option.attr('value', 'true');
	select.append(option);
	
	tr = $('<tr>');
	tr.attr('id', 'tr_2');
	table.append(tr);
	tr.addClass('tagdefcreate');
	td = $('<td>');
	tr.append(td);
	var button = $('<input>');
	button.attr('type', 'button');
	button.val('Define tag');
	button.click(function(event) {defineTag();});
	td.append(button);
	td = $('<td>');
	tr.append(td);
	td = $('<td>');
	tr.append(td);
	td = $('<td>');
	tr.append(td);
	td = $('<td>');
	tr.append(td);
	td = $('<td>');
	tr.append(td);
	var url = getTagdefsURL('user');
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postGetUserTagdefs(data, textStatus, jqXHR, roles);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageTagDefinitions(roles, count)}, delay);
			}
		}
	});
	
}

function postGetUserTagdefs(data, textStatus, jqXHR, roles, count) {
	if (count == null) {
		count = 0;
	}
	var table = $('#User_tagdefs');
	$.each(data, function(i, object) {
		var tr = $('<tr>');
		table.append(tr);
		tr.attr('id', 'tr_' + (i+3));
		tr.addClass('tagdef');
		tr.addClass(roles.contains(object['owner']) ? 'writeok' : 'readonly');
		tr.addClass((++count % 2 == 1) ? 'odd' : 'even');
		var td = $('<td>');
		tr.append(td);
		if (roles.contains(object['owner'])) {
			var input = $('<input>');
			input.attr({'type': 'button',
				'name': 'tag',
				'value': object['tagdef']
			});
			input.val('[X]');
			td.append(input);
			input.click({	'tag': object['tagdef']},
							function(event) {deleteTagdef(event.data.tag, $(this).parent().parent());});
		}
		var a = $('<a>');
		td.append(a);
		a.attr('href', 'javascript:getTagDefinition("tagdef=' + encodeSafeURIComponent(object['tagdef']) + '","tagdef")');
		a.html(object['tagdef']);
		td = $('<td>');
		tr.append(td);
		td.html(object['tagdef type']);
		td = $('<td>');
		tr.append(td);
		td.html(object['tagdef multivalue'] ? '0 or more' : '0 or 1');
		td = $('<td>');
		tr.append(td);
		td.html(object['owner']);
		td = $('<td>');
		tr.append(td);
		td.html(policies[object['tagdef readpolicy']]);
		td = $('<td>');
		tr.append(td);
		td.html(policies[object['tagdef writepolicy']]);
		td = $('<td>');
		tr.append(td);
		td.html(object['tagdef unique'] ? 'True' : 'False');
	});
	var uiDiv = $('#ui');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('System');
	
	// build the table for the system tags
	var table = $('<table>');
	uiDiv.append(table);
	table.addClass('tagdefs');
	table.attr('id', 'System_tagdefs');
	
	// build the header
	var tr = $('<tr>');
	table.append(tr);
	tr.addClass('heading');
	var th = $('<th>');
	tr.append(th);
	th.attr('name', 'tagname');
	th.html('Tag name');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'typestr');
	th.html('Tag type');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'multivalue');
	th.html('# Values');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'owner');
	th.html('Owner');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'readpolicy');
	th.html('Tag readers');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'writepolicy');
	th.html('Tag writers');
	th = $('<th>');
	tr.append(th);
	th.attr('name', 'unique');
	th.html('Tag unique');
	
	var url = getTagdefsURL('system');
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postGetSystemTagdefs(data, textStatus, jqXHR);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){postGetUserTagdefs(data, textStatus, jqXHR, roles, count)}, delay);
			}
		}
	});
}

function postGetSystemTagdefs(data, textStatus, jqXHR) {
	var table = $('#System_tagdefs');
	var count = 0;
	$.each(data, function(i, object) {
		var tr = $('<tr>');
		table.append(tr);
		tr.addClass('tagdef');
		tr.addClass('readonly');
		tr.addClass((++count % 2 == 1) ? 'odd' : 'even');
		var td = $('<td>');
		tr.append(td);
		var a = $('<a>');
		td.append(a);
		a.attr('href', 'javascript:getTagDefinition("tagdef=' + encodeSafeURIComponent(object['tagdef']) + '","tagdef")');
		a.html(object['tagdef']);
		td = $('<td>');
		tr.append(td);
		td.html(object['tagdef type']);
		td = $('<td>');
		tr.append(td);
		td.html(object['tagdef multivalue'] ? '0 or more' : '0 or 1');
		td = $('<td>');
		tr.append(td);
		td.html('');
		td = $('<td>');
		tr.append(td);
		td.html(policies[object['tagdef readpolicy']]);
		td = $('<td>');
		tr.append(td);
		td.html(policies[object['tagdef writepolicy']]);
		td = $('<td>');
		tr.append(td);
		td.html(object['tagdef unique'] ? 'True' : 'False');
	});
}

function defineTag(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/tagdef';
	var obj = new Object();
	obj.action = 'add';
	obj['tag-1'] = $('#tag-1').val();
	obj['type-1'] = $('#type-1').val();
	obj['multivalue-1'] = $('#multivalue-1').val();
	obj['readpolicy-1'] = $('#readpolicy-1').val();
	obj['writepolicy-1'] = $('#writepolicy-1').val();
	obj['unique-1'] = $('#unique-1').val();
	$.ajax({
		url: url,
		type: 'POST',
		data: obj,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postDefineTagdefs(data, textStatus, jqXHR);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){defineTag(count)}, delay);
			}
		}
	});
}

function getTagdefsURL(title) {
	var url = HOME + '/query/tagdef;owner' + ((title == 'system') ? ':absent:' : '');
	url += '(' + encodeURIArray(tagdefsColumns, '').join(';') + ')';
	url += 'tagdef:asc:?limit=none';
	return url;
}

function deleteTagdef(tag, row, count) {
	if (count == null) {
		count = 0;
	}
	var answer = confirm ('Do you want to delete the tag definition "' + tag + '"?');
	if (!answer) {
		return;
	}
	var url = HOME + '/tagdef/' + tag;
	$.ajax({
		url: url,
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postDeleteTagdefs(data, textStatus, jqXHR, row);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){deleteTagdef(tag, row, count)}, delay);
			}
		}
	});
}

function postDefineTagdefs(data, textStatus, jqXHR) {
	var value = $('#tag-1').val();
	var position = 2;
	$.each($('tr', $('#User_tagdefs')), function(i, tr) {
		if (i<3) {
			return true;
		}
		var a = $($('a', $(tr))[0]);
		if (value > a.html()) {
			position = i;
		} else {
			return false;
		}
	});
	var tr = $('<tr>');
	tr.attr('id', 'tr_' + (position+1));
	tr.addClass('tagdef');
	tr.addClass('writeok');
	tr.addClass(((position+1) % 2 == 1) ? 'odd' : 'even');
	var td = $('<td>');
	tr.append(td);
	var input = $('<input>');
	input.attr({'type': 'button',
		'name': 'tag',
		'value': value
	});
	input.val('[X]');
	td.append(input);
	input.click({	'tag': value},
					function(event) {deleteTagdef(event.data.tag, $(this).parent().parent());});
	var a = $('<a>');
	td.append(a);
	a.attr('href', 'javascript:getTagDefinition("tagdef=' + encodeSafeURIComponent(value) + '","tagdef")');
	a.html(value);
	td = $('<td>');
	tr.append(td);
	td.html($('#type-1').val());
	td = $('<td>');
	tr.append(td);
	td.html($('#multivalue-1').val() == 'true' ? '0 or more' : '0 or 1');
	td = $('<td>');
	tr.append(td);
	td.html(USER);
	td = $('<td>');
	tr.append(td);
	td.html(policies[$('#readpolicy-1').val()]);
	td = $('<td>');
	tr.append(td);
	td.html(policies[$('#writepolicy-1').val()]);
	td = $('<td>');
	tr.append(td);
	td.html($('#unique-1').val() == 'true' ? 'True' : 'False');
		
	$('#tag-1').val('');
	$('#type-1').val('empty');
	$('#multivalue-1').val('false');
	$('#readpolicy-1').val('anonymous');
	$('#writepolicy-1').val('anonymous');
	$('#unique-1').val('false');
	
	tr.insertAfter($('#tr_'+position));
	
	$.each($('tr', $('#User_tagdefs')), function(i, row) {
		if (i <= position) {
			return true;
		}
		$(row).attr('id', 'tr_' + i);
		if (i%2 == 1) {
			$(row).removeClass('even');
			$(row).addClass('odd');
		} else {
			$(row).removeClass('odd');
			$(row).addClass('even');
		}
	});
}

function postDeleteTagdefs(data, textStatus, jqXHR, row) {
	row.remove();
	$.each($('tr', $('#User_tagdefs')), function(i, tr) {
		if (i<3) {
			return true;
		}
		$(tr).attr('id', 'tr_' + i);
		if (i%2 == 1) {
			$(tr).removeClass('even');
			$(tr).addClass('odd');
		} else {
			$(tr).removeClass('odd');
			$(tr).addClass('even');
		}
	});
}

function tagsUI(predicate, view, roles, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/' + predicate;
	if (view != null) {
		url = HOME + '/query/' + predicate + '?limit=none&view=' + encodeSafeURIComponent(view);
	}
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postGetTagdefs(data, textStatus, jqXHR, predicate, view, roles);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){tagsUI(predicate, view, roles, count)}, delay);
			}
		}
	});
}

function postGetTagdefs(data, textStatus, jqXHR, predicate, view, roles, count) {
	if (count == null) {
		count = 0;
	}
	var tags = data[0];
	var temp = '';
	$.each(tags, function(key, value) {
		temp += key+'='+value+'\n';
	});
	// get all tags defitions
	var url = HOME + '/query/tagdef';
	url += '(' + encodeURIArray(tagdefsColumns, '').join(';') + ')';
	url += 'tagdef:asc:?limit=none';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postGetAllTagdefs(data, textStatus, jqXHR, tags, predicate, view, roles);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){postGetTagdefs(data, textStatus, jqXHR, predicate, view, roles, count)}, delay);
			}
		}
	});
}

function postGetAllTagdefs(data, textStatus, jqXHR, tags, predicate, view, roles) {
	if (predicate.indexOf('/tags/') == 0) {
		predicate = predicate.substr('/tags/'.length);
	}
	var viewColumns = new Array();
	var isId = (predicate.indexOf('id=') == 0);
	var isFile = false;
	var isURL = false;
	var displayPredicate = predicate;
	var arrPredicate = predicate.split('?');
	if (arrPredicate.length == 2) {
		displayPredicate = arrPredicate[0];
		arrPredicate = arrPredicate[1].split('=');
		if (arrPredicate.length == 2 && arrPredicate[0] == 'view') {
			view = arrPredicate[1];
			predicate = displayPredicate;
		}
	}
	
	$.each(tags, function(key, value) {
		viewColumns.push(key);
	});
	var defaultView = 'default';
	if (tags['config'] != null) {
		defaultView = 'config';
	} else if (tags['tagdef'] != null) {
		defaultView = 'tagdef';
	} else if (tags['typedef'] != null) {
		defaultView = 'typedef';
	} else if (tags['vcontains'] != null) {
		defaultView = 'vcontains';
	} else if (tags['contains'] != null) {
		defaultView = 'contains';
	} else if (tags['bytes'] != null) {
		isFile = true;
		defaultView = 'file';
	} else if (tags['url'] != null) {
		isURL = true;
		defaultView = 'url';
	}
	viewColumns.sort(compareIgnoreCase);
	var allTags = new Object();
	$.each(data, function(i,vals) {
		allTags[vals.tagdef] = vals;
	});
	var uiDiv = $('#ui');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Tag(s) for subject matching "/' + decodeURIComponent(displayPredicate) + '"');
	var div = $('<div>');
	uiDiv.append(div);
	div.addClass('content');
	if (view == 'tagdef' || view == 'typedef' || view == 'file' || view == 'url') {
		var p = $('<p>');
		div.append(p);
		p.html('This is a limited tag view. ');
		var a = $('<a>');
		p.append(a);
		a.attr('href', 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","alltags")');
		a.html('View all tags.');
	}
	var table = $('<table>');
	div.append(table);
	table.addClass('file-list');
	var tr = $('<tr>');
	table.append(tr);
	tr.addClass('file-heading');
	var th = $('<th>');
	tr.append(th);
	th.addClass('tag-name');
	th.html('Tag');
	th = $('<th>');
	tr.append(th);
	th.addClass('file-name');
	a = $('<a>');
	th.append(a);
	a.attr('href', 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","' + defaultView + '")');
	a.html(decodeURIComponent(displayPredicate));
	$.each(viewColumns, function(i, tag) {
		tr = $('<tr>');
		table.append(tr);
		tr.addClass('file');
		tr.addClass(((i+1)%2) == 1 ? 'odd' : 'even');
		var td = $('<td>');
		tr.append(td);
		td.addClass('tag');
		td.addClass('name');
		td.html(tag);
		td = $('<td>');
		tr.append(td);
		td.addClass('file-tag');
		td.addClass(idquote(tag));
		var writeOK = writeAllowed(tag, allTags, roles, tag == 'tagdef' ? tags[tag] : null);
		var valuesTable = null;
		valuesTable = $('<table>');
		td.append(valuesTable);
		valuesTable.addClass('file-tag-list');
		if (tag == 'tagdef') {
			if (tags[tag] != null) {
				a = $('<a>');
				td.append(a);
				a.attr('href', 'javascript:getTagDefinition("tagdef=' + encodeSafeURIComponent(tags[tag]) + '","tagdef")');
				a.html(tags[tag]);
			} else {
				td.html('');
			}
		} else if (tag == 'id') {
			if (isFile || isURL) {
				var userOK = (tags['write users'] == '*') || roles.contains(tags['write users']) || tags['owner'] == USER;
				if (userOK) {
					var idTable = $('<table>');
					td.append(idTable);
					idTable.addClass('file-tag-list');
					var idTr = $('<tr>');
					idTable.append(idTr);
					var idTd = $('<td>');
					idTr.append(idTd);
					idTd.addClass('file-tag id multivalue');
					var multivalueTable = $('<table>');
					idTd.append(multivalueTable);
					var multivalueTr = $('<tr>');
					multivalueTable.append(multivalueTr);
					var multivalueTd = $('<td>');
					multivalueTr.append(multivalueTd);
					var a = $('<a>');
					multivalueTd.append(a);
					a.attr({'href': 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","' + defaultView + '")'});
					a.html(tags['name']);
					var space = $('<label>');
					multivalueTd.append(space);
					space.html(' ');
					a = $('<a>');
					multivalueTd.append(a);
					a.attr({'href': 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","' + defaultView + '")'});
					a.html('(tags)');
					multivalueTd = $('<td>');
					multivalueTr.append(multivalueTd);
					var input = $('<input>');
					input.attr({'type': 'button',
						'value': 'Delete',
						'name': 'Delete',
						'id': 'Delete',
						'onclick': "deleteDataset('" + tags['name'] + "', '" + HOME + '/file/name=' + encodeSafeURIComponent(tags['name']) + "')"
						
					});
					multivalueTd.append(input);
					multivalueTable = $('<table>');
					idTd.append(multivalueTable);
					var formTr = $('<tr>');
					multivalueTable.append(formTr);
					var formTd = $('<td>');
					formTd.attr({'colspan': '2'})
					formTr.append(formTd);
					var form = $('<form>');
					formTd.append(form);
					form.attr({'id': 'NameForm'+tags['id'],
						'name': 'NameForm',
						'enctype': 'application/x-www-form-urlencoded',
						'action': HOME + '/file/name=' + encodeSafeURIComponent(tags['name']),
						'method': 'post',
						'onsubmit': "return validateNameForm('replace', '" + tags['id'] +"')"
					});
					var div = $('<div>');
					form.append(div);
					div.attr({'id': 'NameForm_div'+tags['id']});
					var input = $('<input>');
					input.attr({'type': 'hidden',
						'name': 'action',
						'value': 'put'
					});
					div.append(input);
					var label = $('<label>');
					div.append(label);
					label.html('Replace with:');
					
					var select = $('<select>');
					div.append(select);
					select.attr({'name': 'type',
						'id': 'type'+tags['id'],
						'onchange': "changeNameFormType('replace', '" + tags['id'] + "');"
					});
					var option = $('<option>');
					select.append(option);
					option.text('blank (Dataset node for metadata-only)');
					option.attr('value', 'blank');
					option = $('<option>');
					select.append(option);
					option.text('file (Named dataset for locally stored file)');
					option.attr({'value': 'file',
						'selected': 'selected'});
					option = $('<option>');
					select.append(option);
					option.text('url (Named dataset for URL redirecting)');
					option.attr({'value': 'url'});
					input = $('<input>');
					input.attr({'name': 'myfile'+tags['id'],
						'type': 'file',
						'id': 'fileName'+tags['id']
					});
					input.css({'display': 'inline'});
					div.append(input);
					input = $('<input>');
					input.attr({'type': 'submit',
						'id': 'submit'+tags['id'],
						'value': 'Replace'
					});
					div.append(input);
					div = $('<div>');
					formTd.append(div);
					div.attr({'id': 'Copy'+tags['id']});
				}
			} else if (isId) { 
				var userOK = (tags['write users'] == '*') || roles.contains(tags['write users']) || tags['owner'] == USER;
				if (userOK) {
					var valueTr = $('<tr>');
					valuesTable.removeClass('file-tag-list');
					valuesTable.append(valueTr);
					var valueTd = $('<td>');
					valueTr.append(valueTd);
					var a = $('<a>');
					valueTd.append(a);
					a.attr('href', 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","' + defaultView + '")');
					a.html(predicate + ' (tags)');
					valueTd = $('<td>');
					valueTr.append(valueTd);
					var input = $('<input>');
					input.attr({'type': 'button',
						'value': 'Delete',
						'name': 'Delete',
						'id': 'Delete',
						'onclick': "deleteDataset('" + predicate + "', '" + HOME + '/file/' + predicate + "')"
					});
					valueTd.append(input);
				} else {
					a = $('<a>');
					td.append(a);
					a.attr('href', 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","' + defaultView + '")');
					a.html(predicate + ' (tags)');
				}
			} else {
				a = $('<a>');
				td.append(a);
				a.attr('href', 'javascript:getTagDefinition("' + encodeSafeURIComponent(predicate) + '","' + defaultView + '")');
				a.html(predicate + ' (tags)');
			}
		} else if (tag == 'tagdef type') {
			if (tags[tag] != null) {
				a = $('<a>');
				td.append(a);
				a.attr('href', 'javascript:getTagDefinition("typedef=' + encodeSafeURIComponent(tags[tag]) + '","typedef")');
				a.html('typedef=' + tags[tag]);
			} else {
				td.html('');
			}
		} else if (tags[tag] != null) {
			if ($.isArray(tags[tag])) {
				$.each(tags[tag], function(j, value) {
					var valueTr = $('<tr>');
					valuesTable.append(valueTr);
					var valueTd = $('<td>');
					valueTr.append(valueTd);
					valueTd.addClass('file-tag');
					valueTd.addClass(tag);
					if (allTags[tag]['tagdef multivalue']) {
						valueTd.addClass('multivalue');
					}
					valueTd.html(value);
					if (writeOK) {
						valueTd = $('<td>');
						valueTr.append(valueTd);
						valueTd.addClass('file-tag');
						valueTd.addClass(tag);
						if (allTags[tag]['tagdef multivalue']) {
							valueTd.addClass('multivalue');
						}
						valueTd.addClass('delete');
						var input = $('<input>');
						input.attr({'type': 'button',
							'name': 'tag',
							'value': value
						});
						input.val('Remove Value');
						valueTd.append(input);
						input.click({	'tag': tag,
										'value': value},
										function(event) {removeTagValue(event.data.tag, event.data.value, $(this).parent().parent(), predicate);});
					}
				});
			} else if (allTags[tag]['tagdef type'] == 'boolean') {
				td.html(tags[tag] ? 'True' : 'False');
			} else if (allTags[tag]['tagdef type'] == 'tagpolicy') {
				td.html('' + tags[tag] + ' (' + tagdefPolicies[tags[tag]] + ')');
			} else {
				if (!writeOK) {
					td.html('' + tags[tag]);
				} else {
					var valueTr = $('<tr>');
					valuesTable.append(valueTr);
					var valueTd = $('<td>');
					valueTr.append(valueTd);
					valueTd.addClass('file-tag');
					valueTd.addClass(tag);
					valueTd.addClass('multivalue');
					if (allTags[tag]['tagdef type'] == 'empty') {
						valueTd.html(tags[tag] ? 'is set' : 'not set');
					} else {
						if (tag == 'url') {
							var a = $('<a>');
							valueTd.append(a);
							a.attr({'href': tags[tag]});
							a.html(tags[tag]);
						} else {
							valueTd.html(tags[tag]);
						}
					}
					valueTd = $('<td>');
					valueTr.append(valueTd);
					valueTd.addClass('file-tag');
					valueTd.addClass(tag);
					valueTd.addClass('multivalue');
					valueTd.addClass('delete');
					var input = $('<input>');
					if (allTags[tag]['tagdef type'] == 'empty') {
						input.attr({'type': 'button',
							'name': 'tag',
							'value': tags[tag]
						});
						input.val(tags[tag] ? 'Remove Tag' : 'Set Tag');
						input.click({	'tag': tag,
										'value': tags[tag]},
										function(event) {removeAddTag(event.data.tag, event.data.value, $(this).parent().parent(), predicate);});
					} else {
						input.attr({'type': 'button',
							'name': 'tag',
							'value': tags[tag]
						});
						input.val('Remove Value');
						input.click({	'tag': tag,
										'value': tags[tag]},
										function(event) {removeTagValue(event.data.tag, event.data.value, $(this).parent().parent(), predicate);});
					}
					valueTd.append(input);
				}
			}
		} else {
			if (!writeOK) {
				td.html('');
			}
		}
		if (writeOK && allTags[tag]['tagdef type'] != 'empty') {
			var valueTr = $('<tr>');
			valuesTable.append(valueTr);
			var valueTd = $('<td>');
			valueTr.append(valueTd);
			valueTd.addClass('file-tag');
			valueTd.addClass(tag);
			valueTd.addClass('multivalue');
			var tagType = allTags[tag]['tagdef type'];
			if (tagType == 'text' || tagType == 'int8' || tagType == 'date' || 
					tagType == 'timestamptz' || tagType == 'id' || tagType == 'url') {
				valueTd.addClass('input');
				var input = $('<input>');
				input.attr({'type': 'text',
					'name': 'val_' + tag,
					'id': idquote(tag)+'_id',
					'typestr': 'text'
				});
				valueTd.append(input);
				if (tagType == 'date') {
					var a = $('<a>');
					valueTd.append(a);
					a.attr({'href': "javascript:generateCalendar('" + idquote(tag) + "_id')"});
					var img = $('<img>');
					a.append(img);
					img.attr({'src': HOME + '/static/calendar.gif',
						'width': 16,
						'height': 16,
						'border': 0,
						'alt': 'Pick a date'
					});
				}
			} else if (tagType == 'rolepat' || 
					tagType == 'role' ||
					tagType == 'tagdef' ||
					tagType == 'boolean' ||
					tagType == 'GUI features' ||
					tagType == 'name' ||
					tagType == 'data provider id' ||
					tagType == 'view' ||
					tagType == 'config' ||
					tagType == 'template mode' ||
					tagType == 'vname') {
				valueTd.addClass('input');
				var select = $('<select>');
				valueTd.append(select);
				select.attr({'name': 'val-'+encodeSafeURIComponent(tag),
					'id': idquote(tag)+'_id',
					'typestr': tagType,
					'onclick': "chooseOptions('" + HOME + "', '" + WEBAUTHNHOME + "', '" + tagType + "', '" + idquote(tag) + "_id')"
				});
				var option = $('<option>');
				var text = '';
				if (tagType == 'rolepat') {
					text = 'Choose a Role pattern';
				} else if (tagType == 'role') {
					text = 'Choose a Role';
				} else if (tagType == 'tagdef') {
					text = 'Choose a Tag definition';
				} else if (tagType == 'boolean') {
					text = 'Choose a Boolean (true or false)';
				} else if (tagType == 'GUI features') {
					text = 'Choose a GUI configuration mode';
				} else if (tagType == 'name') {
					text = 'Choose a Subject name';
				} else if (tagType == 'data provider id') {
					text = 'Choose an Enumerated data provider IDs';
				} else if (tagType == 'view') {
					text = 'Choose a View name';
				} else if (tagType == 'config') {
					text = 'Choose a Study Type';
				} else if (tagType == 'template mode') {
					text = 'Choose a Template rendering mode';
				} else if (tagType == 'vname') {
					text = 'Choose a Subject name@version';
				}
				option.text(text);
				option.attr('value', '');
				select.append(option);
			}
			var valueTd = $('<td>');
			valueTr.append(valueTd);
			valueTd.addClass('file-tag');
			valueTd.addClass(tag);
			valueTd.addClass('multivalue');
			valueTd.addClass('set');
			var input = $('<input>');
			input.attr({'type': 'button',
				'name': 'tag'
			});
			input.val('Set Value');
			valueTd.append(input);
			input.click({	'tag': tag},
							function(event) {addTagValue(event.data.tag, $(this).parent().parent(), allTags, predicate);});
		}
	});
	
}

function idquote(value) {
	var ret = '';
	$.each(value, function(i, c) {
		if (c != ' ') {
			ret += c;
		}
	});
	return ret;
}

function writeAllowed(tag, allTags, roles, file) {
	var ret = allTags[tag]['tagdef writepolicy'] == 'anonymous';
	if (file != null) {
		var userOK = roles.contains(allTags[tag]['owner']) || allTags[file]['owner'] == USER || allTags[file]['owner'] == null;
		ret = ret ||
			userOK && !browsersImmutableTags.contains(tag) &&
				(allTags[tag]['tagdef writepolicy'] == 'subject' ||
				allTags[tag]['tagdef writepolicy'] == 'subjectowner' ||
				allTags[tag]['tagdef writepolicy'] == 'tag' ||
				allTags[tag]['tagdef writepolicy'] == 'tagorowner');
	} else {
		var userOK = roles.contains(allTags[tag]['owner']) || allTags[tag]['owner'] == USER  || allTags[tag]['owner'] == 'admin' || allTags[tag]['owner'] == null;
		ret = ret ||
			userOK && !browsersImmutableTags.contains(tag) &&
				(allTags[tag]['tagdef writepolicy'] == 'tag' ||
						allTags[tag]['tagdef writepolicy'] == 'subjectowner' ||
						allTags[tag]['tagdef writepolicy'] == 'tagorowner' ||
						allTags[tag]['tagdef writepolicy'] == 'subject');
	}
	return ret;
}

function removeTagValue(tag, value, row, predicate, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/tags/' + predicate;
	var obj = new Object();
	obj.action = 'delete';
	obj['tag'] = tag;
	obj['value'] = value;
	$.ajax({
		url: url,
		type: 'POST',
		data: obj,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			row.remove();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){removeTagValue(tag, value, row, predicate, count)}, delay);
			}
		}
	});
}

function removeAddTag(tag, value, row, predicate, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/tags/' + predicate;
	var obj = new Object();
	obj.action = value ? 'delete' : 'put';
	obj['tag'] = tag;
	$.ajax({
		url: url,
		type: 'POST',
		data: obj,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postRemoveAddTag(tag, value, row, predicate);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){removeAddTag(tag, value, row, predicate, count)}, delay);
			}
		}
	});
}

function postRemoveAddTag(tag, value, row, predicate) {
	var valueTr = $('<tr>');
	valueTr.insertBefore(row);
	var valueTd = $('<td>');
	valueTr.append(valueTd);
	valueTd.addClass('file-tag');
	valueTd.addClass(tag);
	valueTd.addClass('multivalue');
	valueTd.html(!value ? 'is set' : 'not set');
	valueTd = $('<td>');
	valueTr.append(valueTd);
	valueTd.addClass('file-tag');
	valueTd.addClass(tag);
	valueTd.addClass('multivalue');
	valueTd.addClass('delete');
	var input = $('<input>');
	input.attr({'type': 'button',
		'name': 'tag',
		'value': !value
	});
	input.val(!value ? 'Remove Tag' : 'Set Tag');
	input.click({	'tag': tag,
					'value': !value},
					function(event) {removeAddTag(event.data.tag, event.data.value, $(this).parent().parent(), predicate);});
	valueTd.append(input);
	row.remove();
}

function addTagValue(tag, row, allTags, predicate, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/tags/' + predicate;
	var obj = new Object();
	obj.action = 'put';
	obj['set-'+tag] = true;
	obj['val-'+tag] = $('#'+idquote(tag)+'_id').val();
	$.ajax({
		url: url,
		type: 'POST',
		data: obj,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postAddTagValue(tag, row, allTags, predicate);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){addTagValue(tag, row, allTags, predicate, count)}, delay);
			}
		}
	});

}

function postAddTagValue(tag, row, allTags, predicate) {
	var value = $('#'+idquote(tag)+'_id').val();
	var valueTr = $('<tr>');
	valueTr.insertBefore(row);
	var valueTd = $('<td>');
	valueTr.append(valueTd);
	valueTd.addClass('file-tag');
	valueTd.addClass(tag);
	valueTd.addClass('multivalue');
	if (tag == 'url') {
		var a = $('<a>');
		valueTd.append(a);
		a.attr({'href': value});
		a.html(value);
	} else {
		valueTd.html(tags[tag]);
	}
	valueTd = $('<td>');
	valueTr.append(valueTd);
	valueTd.addClass('file-tag');
	valueTd.addClass(tag);
	valueTd.addClass('multivalue');
	valueTd.addClass('delete');
	var input = $('<input>');
	input.attr({'type': 'button',
		'name': 'tag',
		'value': value
	});
	input.val('Remove Value');
	valueTd.append(input);
	input.click({	'tag': tag,
					'value': value},
					function(event) {removeTagValue(event.data.tag, event.data.value, $(this).parent().parent(), predicate);});
	$('#'+idquote(tag)+'_id').val('');
	if (!allTags[tag]['tagdef multivalue']) {
		valueTr.prev().remove();
	}
}

function userInfo(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/session'
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postUserInfo(data);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){userInfo(count)}, delay);
			}
		}
	});
}

function postUserInfo(data) {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Status: Logged In');
	var p = $('<p>');
	uiDiv.append(p);
	var since = getLocaleTimestamp(data['since']);
	since = since.split(" ")[1].split('.')[0];
	p.html('You are logged in as "serban" since ' + since + '.');
	var roles = [];
	$.each(data.attributes, function (i, val) {
		if (val != USER) {
			roles.push(val);
		}
	});
	if (roles.length > 0) {
		roles.sort(compareIgnoreCase);
		var p = $('<p>');
		uiDiv.append(p);
		p.html('As such, you are assigned to the following attributes:');
		var ul = $('<ul>');
		uiDiv.append(ul);
		$.each(roles, function (i, role) {
			var li = $('<li>');
			ul.append(li);
			li.html(role);
		});
	}
}

function userLogout() {
	var url = HOME + '/session';
	$.ajax({
		url: url,
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		success: function(data, textStatus, jqXHR) {
			$('#topmenu').html('');
			$('#authninfo').html('');
			window.location = HOME;
		},
		error: function(jqXHR, textStatus, errorThrown) {
			handleError(jqXHR, textStatus, errorThrown, MAX_RETRIES + 1, url);
		}
	});
}

function userChangePassword() {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Change Password');
	var fieldset = $('<fieldset>');
	uiDiv.append(fieldset);
	var legend = $('<legend>');
	fieldset.append(legend);
	legend.html('User ' + USER);
	var table = $('<table>');
	fieldset.append(table);
	var tr = $('<tr>');
	table.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.html('Old Password:');
	td = $('<td>');
	tr.append(td);
	var input = $('<input>');
	input.attr({'type': 'password',
		'name': 'oldpassword',
		'id': 'oldpassword',
		'size': '15'
		
	});
	td.append(input);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.html('New Password:');
	td = $('<td>');
	tr.append(td);
	input = $('<input>');
	input.attr({'type': 'password',
		'name': 'newpassword1',
		'id': 'newpassword1',
		'size': '15'
		
	});
	td.append(input);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.html('New Password (confirm):');
	td = $('<td>');
	tr.append(td);
	input = $('<input>');
	input.attr({'type': 'password',
		'name': 'newpassword2',
		'id': 'newpassword2',
		'size': '15'
		
	});
	td.append(input);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	input = $('<input>');
	input.attr({'type': 'button',
		'value': 'Change Password',
		'onclick': 'changePassword();'
	});
	td.append(input);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	input = $('<input>');
	input.attr({'type': 'button',
		'value': 'Cancel',
		'onclick': 'homePage();'
	});
	td.append(input);
	uiDiv.append($('<br>'));
	uiDiv.append($('<br>'));
	var div = $('<div>');
	uiDiv.append(div);
	div.addClass('error');
	div.attr({'id': 'errorDiv'});
}

function changePassword(count) {
	var oldpassword = $('#oldpassword').val().replace(/^\s*/, "").replace(/\s*$/, "");
	if (oldpassword == '') {
		alert('Please provide the old password.');
		return;
	}
	var newpassword1 = $('#newpassword1').val().replace(/^\s*/, "").replace(/\s*$/, "");
	if (newpassword1 == '') {
		alert('Please provide the new password.');
		return;
	}
	var newpassword2 = $('#newpassword2').val().replace(/^\s*/, "").replace(/\s*$/, "");
	if (newpassword2 == '') {
		alert('Please confirm the new password.');
		return;
	}
	if (newpassword1 != newpassword2) {
		alert('The confirm new password is invalid.');
		return;
	}
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/password';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		type: 'PUT',
		data: {'old_password': oldpassword,
			'password': newpassword1
		},
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postChangePassword(data, textStatus, jqXHR);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (jqXHR.status == 403) {
				$('#errorDiv').html(jqXHR.responseText);
				return;
			}
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){changePassword(count)}, delay);
			}
		}
	});
}

function postChangePassword() {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var div = $('<div>');
	uiDiv.append(div);
	div.addClass('transmissionnum');
	div.html('The password was successfully changed.');
}

function homePage(count) {
	// get the list on homepage files
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/query/' + encodeSafeURIComponent('list on homepage') + '(name;onclick)name:asc:';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postHomePage(data, textStatus, jqXHR);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){homePage(count)}, delay);
			}
		}
	});
}

function postHomePage(data, textStatus, jqXHR) {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var ol = $('<ol>');
	uiDiv.append(ol);
	$.each(data, function(i, entry) {
		var li = $('<li>');
		ol.append(li);
		a = $('<a>');
		li.append(a);
		a.attr({'href': entry.onclick});
		a.html(entry.name);
	});
}

function manageAttributes(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/attribute';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postManageAttributes(data, textStatus, jqXHR);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageAttributes(count)}, delay);
			}
		}
	});
}

function manageUsers(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/user';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postManageUsers(data, textStatus, jqXHR);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageUsers(count)}, delay);
			}
		}
	});
}

function postManageUsers(data, textStatus, jqXHR) {
	var users = data;
	users.sort(compareIgnoreCase);
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('User Management');
	h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Create an User');
	var input = $('<input>');
	input.attr({'type': 'text',
		'name': 'role',
		'id': 'role'
	});
	uiDiv.append(input);
	input = $('<input>');
	input.attr({'type': 'button',
		'value': 'Create',
		'id': 'createRole',
		'onclick': 'createUser();'
	});
	uiDiv.append(input);
	h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Existing Users');
	var p = $('<p>');
	uiDiv.append(p);
	var a = $('<a>');
	p.append(a);
	a.attr({'href': 'javascript:manageAllRoles()'});
	a.html('Manage attributes of all users');
	var table = $('<table>');
	uiDiv.append(table);
	table.addClass('role-list');
	var tr = $('<tr>');
	table.append(tr);
	var th = $('<th>');
	tr.append(th);
	th.html('User');
	th = $('<th>');
	tr.append(th);
	th.html('Delete');
	th = $('<th>');
	tr.append(th);
	th.html('Disable');
	th = $('<th>');
	tr.append(th);
	th.html('Reset');
	th = $('<th>');
	tr.append(th);
	th.html('Attributes');
	$.each(users, function(i, user) {
		tr = $('<tr>');
		table.append(tr);
		tr.addClass('role');
		var td = $('<td>');
		tr.append(td);
		td.html(user);
		td = $('<td>');
		tr.append(td);
		input = $('<input>');
		input.attr({'type': 'button',
			'value': 'Delete user',
			'onclick': 'deleteUser("' + user + '");'
		});
		td.append(input);
		td = $('<td>');
		tr.append(td);
		input = $('<input>');
		input.attr({'type': 'button',
			'value': 'Disable login',
			'onclick': 'disableLogin("' + user + '");'
		});
		td.append(input);
		td = $('<td>');
		tr.append(td);
		input = $('<input>');
		input.attr({'type': 'button',
			'value': 'Reset password',
			'onclick': 'resetPassword("' + user + '");'
		});
		td.append(input);
		td = $('<td>');
		tr.append(td);
		a = $('<a>');
		td.append(a);
		a.attr({'href': 'javascript:manageUserRoles("' + user + '")'});
		a.html('Manage attributes');
	});
}

function postManageAttributes(data, textStatus, jqXHR) {
	var attributes = data;
	attributes.sort(compareIgnoreCase);
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Attribute Management');
	h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Create an Attribute');
	var input = $('<input>');
	input.attr({'type': 'text',
		'name': 'attribute',
		'id': 'attribute'
	});
	uiDiv.append(input);
	input = $('<input>');
	input.attr({'type': 'button',
		'value': 'Create',
		'onclick': 'buildAttribute();'
	});
	uiDiv.append(input);
	h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Existing Attributes');
	var p = $('<p>');
	uiDiv.append(p);
	var table = $('<table>');
	uiDiv.append(table);
	table.addClass('role-list');
	var tr = $('<tr>');
	table.append(tr);
	var th = $('<th>');
	tr.append(th);
	th.html('Attribute');
	th = $('<th>');
	tr.append(th);
	th.html('Delete');
	$.each(attributes, function(i, attribute) {
		tr = $('<tr>');
		table.append(tr);
		tr.addClass('role');
		var td = $('<td>');
		tr.append(td);
		td.html(attribute);
		td = $('<td>');
		tr.append(td);
		input = $('<input>');
		input.attr({'type': 'button',
			'value': 'Delete attribute',
			'onclick': 'deleteGlobalAttribute("' + attribute + '");'
		});
		td.append(input);
	});
}

function manageAllRoles(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/user';
	$.ajax({
		url: url,
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			manageAllUsersAttributes(data);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageAllRoles(count)}, delay);
			}
		}
	});
}

function deleteUser(user, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/user/' + encodeSafeURIComponent(user);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			manageUsers();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){deleteUser(user, count)}, delay);
			}
		}
	});
}

function deleteGlobalAttribute(attribute, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/attribute/' + encodeSafeURIComponent(attribute);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			manageAttributes();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){deleteGlobalAttribute(attribute, count)}, delay);
			}
		}
	});
}

function manageMembership(allAttributes, user, count) {
	if (count == null) {
		count = 0;
	}
	// get user attributes
	var url = HOME + '/user/' + encodeSafeURIComponent(user) + '/attribute';
	$.ajax({
		url: url,
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postManageUserAttributes(data, allAttributes, user);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageMembership(allAttributes, user, count)}, delay);
			}
		}
	});
}

function postManageUserAttributes(userAttributes, allAtrributes, user) {
	userAttributes.sort(compareIgnoreCase);
	var fieldset = $('#fieldset_' + idquote(user));
	if (userAttributes.length > 0 || allAtrributes.length > 0) {
		var table = $('<table>');
		fieldset.append(table);
		var tr = $('<tr>');
		table.append(tr);
		if (allAtrributes.length > userAttributes.length) {
			td = $('<td>');
			tr.append(td);
			td.attr({'valign': 'top',
				'id': 'td_assign_attribute_' + idquote(user)});
			fieldset = $('<fieldset>');
			td.append(fieldset);
			legend = $('<legend>');
			fieldset.append(legend);
			legend.html('Assign attribute');
			var select = $('<select>');
			fieldset.append(select);
			select.attr({'id': 'attribute_' + idquote(user),
				'name': 'attributeName'});
			$.each(allAtrributes, function(i, val) {
				if (!userAttributes.contains(val)) {
					var option = $('<option>');
					select.append(option);
					option.text(val);
					option.attr('value', val);
				}
			});
			fieldset.append($('<br>'));
			var input = $('<input>');
			input.attr({'type': 'button',
				'name': 'assignAttribute_' + idquote(user), 
				'id': 'assignAttribute_' + idquote(user),
				'value': 'Assign Attribute',
				'onclick': 'assignAttribute("' + user + '")'
			});
			fieldset.append(input);
		}
		if (userAttributes.length > 0) {
			td = $('<td>');
			tr.append(td);
			td.attr({'valign': 'top',
				'id': 'td_remove_attribute_' + idquote(user)});
			fieldset = $('<fieldset>');
			td.append(fieldset);
			legend = $('<legend>');
			fieldset.append(legend);
			legend.html('Current attributes');
			var table = $('<table>');
			fieldset.append(table);
			table.attr({'border': '1',
				'id': 'table_attribute_' + idquote(user)});
			$.each(userAttributes, function(i, val) {
				var tr = $('<tr>');
				table.append(tr);
				var td = $('<td>');
				tr.append(td);
				td.addClass('userAttribute');
				td.html(val);
				td = $('<td>');
				tr.append(td);
				var input = $('<input>');
				input.attr({'type': 'button',
					'name': 'removeUserAttribute_' + idquote(user) + '_' + idquote(val), 
					'id': 'removeUserAttribute_' + idquote(user) + '_' + idquote(val),
					'value': 'Remove',
					'onclick': 'removeUserAttribute("' + user + '", "' + val + '")'
				});
				td.append(input);
			});
		}
	}
}

function assignAttribute(user, count) {
	if (count == null) {
		count = 0;
	}
	var attribute = $('#attribute_' + idquote(user)).val();
	var url = HOME + '/user/' + encodeSafeURIComponent(user) + '/attribute/' + encodeSafeURIComponent(attribute);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'PUT',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			// to re-write success
			if ($('#td_remove_attribute_' + idquote(user)).length == 0) {
				td = $('<td>');
				td.insertAfter($('#td_assign_attribute_' + idquote(user)));
				td.attr({'valign': 'top',
					'id': 'td_remove_attribute_' + idquote(user)});
				fieldset = $('<fieldset>');
				td.append(fieldset);
				legend = $('<legend>');
				fieldset.append(legend);
				legend.html('Current attributes');
				var table = $('<table>');
				fieldset.append(table);
				table.attr({'border': '1',
					'id': 'table_attribute_' + idquote(user)});
			}
			var allAttributes = new Array();
			var userAttributes = new Array();
			userAttributes.push(attribute);
			$.each($('option', $('#attribute_' + idquote(user))), function (i, option) {
				if ($(option).attr('value') != attribute) {
					allAttributes.push($(option).attr('value'));
				}
			});
			$.each($('.userAttribute', $('#table_attribute_' + idquote(user))), function (i, td) {
				userAttributes.push($(td).html());
			});
			allAttributes.sort(compareIgnoreCase);
			userAttributes.sort(compareIgnoreCase);
			if (allAttributes.length > 0) {
				var select = $('#attribute_' + idquote(user));
				select.html('');
				$.each(allAttributes, function(i, val) {
					var option = $('<option>');
					select.append(option);
					option.text(val);
					option.attr('value', val);
				});
			} else {
				$('#td_assign_attribute_' + idquote(user)).remove();
			}
			var table = $('#table_attribute_' + idquote(user));
			table.html('');
			$.each(userAttributes, function(i, val) {
				var tr = $('<tr>');
				table.append(tr);
				var td = $('<td>');
				tr.append(td);
				td.addClass('userAttribute');
				td.html(val);
				td = $('<td>');
				tr.append(td);
				var input = $('<input>');
				input.attr({'type': 'button',
					'name': 'removeUserAttribute_' + idquote(user) + '_' + idquote(val), 
					'id': 'removeUserAttribute_' + idquote(user) + '_' + idquote(val),
					'value': 'Remove',
					'onclick': 'removeUserAttribute("' + user + '", "' + val + '")'
				});
				td.append(input);
			});
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){assignAttribute(user, count)}, delay);
			}
		}
	});
}

function removeUserAttribute(user, attribute, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/user/' + encodeSafeURIComponent(user) + '/attribute/' + encodeSafeURIComponent(attribute);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			if ($('#td_assign_attribute_' + idquote(user)).length == 0) {
				td = $('<td>');
				td.insertBefore($('#td_remove_attribute_' + idquote(user)));
				td.attr({'valign': 'top',
					'id': 'td_assign_attribute_' + idquote(user)});
				fieldset = $('<fieldset>');
				td.append(fieldset);
				legend = $('<legend>');
				fieldset.append(legend);
				legend.html('Assign attribute');
				var select = $('<select>');
				fieldset.append(select);
				select.attr({'id': 'attribute_' + idquote(user),
					'name': 'attributeName'});
				fieldset.append($('<br>'));
				var input = $('<input>');
				input.attr({'type': 'button',
					'name': 'assignAttribute_' + idquote(user), 
					'id': 'assignAttribute_' + idquote(user),
					'value': 'Assign Attribute',
					'onclick': 'assignAttribute("' + user + '")'
				});
				fieldset.append(input);
			}
			var allAttributes = new Array();
			var userAttributes = new Array();
			allAttributes.push(attribute);
			$.each($('option', $('#attribute_' + idquote(user))), function (i, option) {
				allAttributes.push($(option).attr('value'));
			});
			$.each($('.userAttribute', $('#table_attribute_' + idquote(user))), function (i, td) {
				if ($(td).html() != attribute) {
					userAttributes.push($(td).html());
				}
			});

			allAttributes.sort(compareIgnoreCase);
			userAttributes.sort(compareIgnoreCase);
			var select = $('#attribute_' + idquote(user));
			select.html('');
			$.each(allAttributes, function(i, val) {
				var option = $('<option>');
				select.append(option);
				option.text(val);
				option.attr('value', val);
			});
			
			if (userAttributes.length > 0) {
				var table = $('#table_attribute_' + idquote(user));
				table.html('');
				$.each(userAttributes, function(i, val) {
					var tr = $('<tr>');
					table.append(tr);
					var td = $('<td>');
					tr.append(td);
					td.addClass('userAttribute');
					td.html(val);
					td = $('<td>');
					tr.append(td);
					var input = $('<input>');
					input.attr({'type': 'button',
						'name': 'removeUserAttribute_' + idquote(user) + '_' + idquote(val), 
						'id': 'removeUserAttribute_' + idquote(user) + '_' + idquote(val),
						'value': 'Remove',
						'onclick': 'removeUserAttribute("' + user + '", "' + val + '")'
					});
					td.append(input);
				});
			} else {
				$('#td_remove_attribute_' + idquote(user)).remove();
			}
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){removeUserAttribute(user, attribute, count)}, delay);
			}
		}
	});
}

function resetPassword(user, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/password/' + encodeSafeURIComponent(user);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'PUT',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postResetPassword(data, user);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){resetPassword(user, count)}, delay);
			}
		}
	});
}

function postResetPassword(data, user) {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var p = $('<p>');
	uiDiv.append(p);
	p.html('The password for "' + user + '" has been reset.')
	var ul = $('<ul>');
	uiDiv.append(ul);
	var li = $('<li>');
	ul.append(li);
	li.html('New password: "' + data[user] + '"')
}

function disableLogin(user, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/password/' + encodeSafeURIComponent(user);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'DELETE',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			alert('The password for the user "' + user + '" was disabled.');
		},
		error: function(jqXHR, textStatus, errorThrown) {
			if (jqXHR.status == 404) {
				// NotFound
				alert('The password is already disabled for ' + jqXHR.responseText);
				return;
			} else if (jqXHR.status == 404) {
				// Forbidden
				alert(jqXHR.responseText);
				return;
			}
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){disableLogin(user, count)}, delay);
			}
		}
	});
}

function createUser(count) {
	if (count == null) {
		count = 0;
	}
	var role = $('#role').val().replace(/^\s*/, "").replace(/\s*$/, "");
	if (role == '') {
		alert('Please provide a name for the new user.');
		return;
	}
	var url = HOME + '/user/' + encodeSafeURIComponent(role);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'PUT',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			manageUsers();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){createUser(count)}, delay);
			}
		}
	});
}

function buildAttribute(count) {
	if (count == null) {
		count = 0;
	}
	var attribute = $('#attribute').val().replace(/^\s*/, "").replace(/\s*$/, "");
	if (attribute == '') {
		alert('Please provide a name for the new attribute.');
		return;
	}
	var url = HOME + '/attribute/' + encodeSafeURIComponent(attribute);
	$.ajax({
		url: url,
		dataType: 'json',
		type: 'PUT',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			manageAttributes();
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){buildAttribute(count)}, delay);
			}
		}
	});
}

function queryByTags() {
	viewLink(null);
}

function viewAvailableTagDefinitions() {
	viewLink('tagdef?view=tagdef');
}

function viewLink(querypath, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/ui/query/'
	if (querypath != null) {
		url += querypath;
	}
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			renderQuery(data);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){viewLink(querypath, count)}, delay);
			}
		}
	});
}

function renderQuery(data) {
	renderQueryHTML();
	initPSOC(HOME, USER, WEBAUTHNHOME, data.basepath, data.querypath);
}

function renderQueryHTML() {
	var uiDiv = $('#ui');
	uiDiv.html('');
	$('#selectViewDiv').remove();
	$('#customizedViewDiv').remove();
	
	var psoc = $('<div>');
	uiDiv.append(psoc);
	psoc.attr({'id': 'psoc',
		'onmouseup': "document.body.style.cursor = 'default';"});
	
	//<!-- Table Cell Right Click Menu -->
	var ul = $('<ul>');
	psoc.append(ul);
	ul.attr({'id': 'tablecellMenu'});
	ul.addClass('contextMenu');
	var li = $('<li>');
	ul.append(li);
	var a = $('<a>');
	li.append(a);
	a.attr({'href': '#delete'});
	a.html('Delete value');
	
	li = $('<li>');
	ul.append(li);
	a = $('<a>');
	li.append(a);
	a.attr({'href': '#bulkdelete'});
	a.html('Delete values...');
	
	li = $('<li>');
	ul.append(li);
	a = $('<a>');
	li.append(a);
	a.attr({'href': '#edit'});
	a.html('Edit value');
	
	ul = $('<ul>');
	psoc.append(ul);
	ul.attr({'id': 'tablecellEditMenu'});
	ul.addClass('contextMenu');
	li = $('<li>');
	ul.append(li);
	a = $('<a>');
	li.append(a);
	a.attr({'href': '#edit'});
	a.html('Edit value');
	
	var table = $('<table>');
	psoc.append(table);
	var thead = $('<thead>');
	table.append(thead);
	var tr = $('<tr>');
	thead.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.addClass('topnav');
	var b = $('<b>');
	td.append(b);
	b.html('Actions');
	
	ul = $('<ul>');
	td.append(ul);
	ul.attr({'id': 'GlobalMenu'});
	ul.addClass('subnav');
	li = $('<li>');
	ul.append(li);
	li.attr({'id': 'clearAllFilters',
		'onmousedown': 'clearAllFilters();'});
	li.addClass('item');
	li.html('Clear all filters');
	
	li = $('<li>');
	ul.append(li);
	li.attr({'id': 'disableEdit',
		'onmousedown': 'disableEdit();'});
	li.addClass('item');
	li.html('Disable edit');
	li.css('display', 'none');
	
	li = $('<li>');
	ul.append(li);
	li.attr({'id': 'enableEdit',
		'onmousedown': 'enableEdit();'});
	li.addClass('item');
	li.html('Enable edit');
	li.css('display', 'none');
	
	li = $('<li>');
	ul.append(li);
	li.attr({'id': 'hideRange',
		'onmousedown': 'hideRange();'});
	li.addClass('item');
	li.html('Hide range');
	li.css('display', 'none');
	
	li = $('<li>');
	ul.append(li);
	li.attr({'onmousedown': 'addTagToQuery();'});
	li.addClass('item');
	li.html('Show another column...');
	
	li = $('<li>');
	ul.append(li);
	li.attr({'onmousedown': 'addViewTagsToQuery();'});
	li.addClass('item');
	li.html('Show a column set...');
	
	li = $('<li>');
	ul.append(li);
	li.attr({'id': 'showRange',
		'onmousedown': 'showRange();'});
	li.addClass('item');
	li.html('Show range');
	var span = $('<span>')
	td.append(span);
	
	td = $('<td>');
	tr.append(td);
	span = $('<span>')
	td.append(span);
	span.attr({'id': 'ViewResults'});
	var img = $('<img>');
	td.append(img);
	img.attr({'id': 'pagePrevious',
		'src': HOME + '/static/back.jpg',
		'alt': 'Previous',
		'onclick': 'setPreviousPage();'});
	img.addClass('margin');
	var label = $('<label>');
	td.append(label);
	label.attr({'id': 'resultsRange'});
	var img = $('<img>');
	td.append(img);
	img.attr({'id': 'pageNext',
		'src': HOME + '/static/forward.jpg',
		'alt': 'Previous',
		'onclick': 'setNextPage();'});
	img.addClass('margin');
	span = $('<span>')
	td.append(span);
	span.attr({'id': 'totalResults'});
	label = $('<label>');
	td.append(label);
	label.html(' with');
	var select = $('<select>');
	td.append(select);
	select.attr({'id': 'previewLimit',
		'name': 'previewLimit',
		'onchange': 'updatePreviewLimit()'});
	var option = $('<option>');
	select.append(option);
	option.text('10');
	option.attr('value', '10');
	option = $('<option>');
	select.append(option);
	option.text('25');
	option.attr('value', '25');
	option = $('<option>');
	select.append(option);
	option.text('50');
	option.attr('value', '50');
	option = $('<option>');
	select.append(option);
	option.text('100');
	option.attr('value', '100');
	label = $('<label>');
	td.append(label);
	label.html('per page.');

	td = $('<td>');
	tr.append(td);
	a = $('<a>');
	td.append(a);
	a.attr({'href': '',
		'id': 'Query_URL'});
	a.html('Bookmarkable link');

	var div = $('<div>');
	psoc.append(div);
	div.attr({'id': 'customizedViewDiv'});
	div.css({'display': 'none'});
	var fieldset = $('<fieldset>');
	div.append(fieldset);
	var p = $('<p>');
	fieldset.append(p);
	p.html("Select an available tag and click 'Add to query':");
	p = $('<p>');
	fieldset.append(p);
	var input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'showAnotherColumn',
		'value': 'add'});
	p.append(input);
	label = $('<label>');
	p.append(label);
	label.html('Add to visible columns');
	var br = $('<br>');
	p.append(br);
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'showAnotherColumn',
		'value': 'replace'});
	p.append(input);
	label = $('<label>');
	p.append(label);
	label.html('Replace previously visible columns');
	br = $('<br>');
	p.append(br);
	select = $('<select>');
	fieldset.append(select);
	select.attr({'id': 'customizedViewSelect',
		'name': 'customizedViewSelect',
		'onclick': "loadAvailableTags('customizedViewSelect')"});
	option = $('<option>');
	select.append(option);
	option.text('Available tags');
	option.attr('value', '');
	
	div = $('<div>');
	psoc.append(div);
	div.attr({'id': 'selectViewDiv'});
	div.css({'display': 'none'});
	fieldset = $('<fieldset>');
	div.append(fieldset);
	p = $('<p>');
	fieldset.append(p);
	p.html("Select an available view and click 'Add to query':");
	p = $('<p>');
	fieldset.append(p);
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'showColumnSet',
		'value': 'add'});
	p.append(input);
	label = $('<label>');
	p.append(label);
	label.html('Add to visible columns');
	br = $('<br>');
	p.append(br);
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'showColumnSet',
		'value': 'replace'});
	p.append(input);
	label = $('<label>');
	p.append(label);
	label.html('Replace previously visible columns');
	br = $('<br>');
	p.append(br);
	select = $('<select>');
	fieldset.append(select);
	select.attr({'id': 'selectViews',
		'name': 'selectViews',
		'onclick': "loadAvailableViews('selectViews')"});
	option = $('<option>');
	select.append(option);
	option.text('Available Views');
	option.attr('value', '');
	
	div = $('<div>');
	psoc.append(div);
	div.attr({'id': 'queryDiv'});
	div.css({'display': 'none',
		'width': '25%'});
	
	var divWrapper = $('<div>');
	psoc.append(divWrapper);
	divWrapper.attr({'id': 'editTagValuesWrapperDiv'});
	divWrapper.css({'display': 'none',
		'width': '25%'});
	div = $('<div>');
	divWrapper.append(div);
	div.attr({'id': 'editTagValuesDiv'});
	fieldset = $('<fieldset>');
	div.append(fieldset);
	var legend = $('<legend>');
	fieldset.append(legend);
	legend.html('Scope');
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'valuesScope',
		'value': 'page'});
	fieldset.append(input);
	label = $('<label>');
	fieldset.append(label);
	label.html('Edit all subjects showing on this page');
	br = $('<br>');
	fieldset.append(br);
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'valuesScope',
		'value': 'filter'});
	fieldset.append(input);
	label = $('<label>');
	fieldset.append(label);
	label.html('Edit all subjects matching filters');
	br = $('<br>');
	fieldset.append(br);

	fieldset = $('<fieldset>');
	div.append(fieldset);
	legend = $('<legend>');
	fieldset.append(legend);
	legend.html('Action');
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'valuesAction',
		'value': 'PUT'});
	fieldset.append(input);
	label = $('<label>');
	fieldset.append(label);
	label.html('Add tag value(s)');
	br = $('<br>');
	fieldset.append(br);
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'valuesAction',
		'value': 'DELETE'});
	fieldset.append(input);
	label = $('<label>');
	fieldset.append(label);
	label.html('Delete tag value(s)');
	br = $('<br>');
	fieldset.append(br);
	br = $('<br>');
	div.append(br);
	table = $('<table>');
	div.append(table);
	table.attr({'id': 'bulk_edit_table'});


	divWrapper = $('<div>');
	psoc.append(divWrapper);
	divWrapper.attr({'id': 'deleteTagValuesWrapperDiv'});
	divWrapper.css({'display': 'none',
		'width': '25%'});
	div = $('<div>');
	divWrapper.append(div);
	div.attr({'id': 'deleteTagValuesDiv'});
	fieldset = $('<fieldset>');
	div.append(fieldset);
	legend = $('<legend>');
	fieldset.append(legend);
	legend.html('Scope');
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'deleteValuesScope',
		'value': 'page'});
	fieldset.append(input);
	label = $('<label>');
	fieldset.append(label);
	label.html('Edit all subjects showing on this page');
	br = $('<br>');
	fieldset.append(br);
	input = $('<input>');
	input.attr({'type': 'radio',
		'name': 'deleteValuesScope',
		'value': 'filter'});
	fieldset.append(input);
	label = $('<label>');
	fieldset.append(label);
	label.html('Edit all subjects matching filters');
	br = $('<br>');
	fieldset.append(br);
	div.append($('<br>'))
	label = $('<label>');
	div.append(label);
	label.html('Values:');
	div.append($('<br>'))
	table = $('<table>');
	div.append(table);
	var tbody = $('<tbody>');
	table.append(tbody);
	tbody.attr({'id': 'deleteTagValuesTableBody'});
	
	div = $('<div>');
	psoc.append(div);
	div.attr({'id': 'Query_Preview'});

	select = $('<select>');
	psoc.append(select);
	select.attr({'id': 'versions',
		'name': 'versions',
		'onchange': 'showPreview()'});
	option = $('<option>');
	select.append(option);
	option.text('Show latest version if matches');
	option.attr('value', 'latest');
	option = $('<option>');
	select.append(option);
	option.text('Show any version which matches');
	option.attr('value', 'any');

	div = $('<div>');
	psoc.append(div);
	div.attr({'id': 'DragAndDropBox'});
	div.css({'display': 'none',
	    'position': 'absolute',
	    'font-size': '12px',
	    'font-weight': 'bold',
	    'font-family': 'verdana',
	    'border': '#72B0E6 solid 1px',
	    'padding': '15px',
	    'color': '#1A80DB',
    	'background-color': '#FFFFFF'});

	div = $('<div>');
	psoc.append(div);
	div.attr({'id': 'TipBox'});
	div.css({'display': 'none',
	    'position': 'absolute',
	    'font-size': '12px',
	    'font-weight': 'bold',
	    'font-family': 'verdana',
	    'border': '#72B0E6 solid 1px',
	    'padding': '15px',
	    'color': '#1A80DB',
	    'white-space': 'nowrap',
    	'background-color': '#FFFFFF'});
}

function manageAvailableTagDefinitions(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/session'
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			USER_ROLES = data['attributes'];
			USER = data['client'];
			manageTagDefinitions(data['attributes']);
			/*
			var uiopts = {'path': [[[{'tag': 'tagdef',
			                         'vals': ['MyTag']}]]],
					'queryopts': {'limit': 'none',
						'view': 'tagdef'}
					
			};
			alert(uiopts.path[0][0][0].tag +' = ' + uiopts.path[0][0][0].vals[0]);
			alert(uiopts.queryopts.view);
			*/
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageAvailableTagDefinitions(count)}, delay);
			}
		}
	});
}

function createCustomDataset() {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var form = $('<form>');
	uiDiv.append(form);
	form.attr({'id': 'NameForm',
		'name': 'NameForm',
		'enctype': 'application/x-www-form-urlencoded',
		'action': HOME + '/file',
		'method': 'post',
		'onsubmit': "return validateNameForm('create', '')"
	});
	div = $('<div>');
	form.append(div);
	div.attr({'id': 'NameForm_div'});
	var h3 = $('<h3>');
	div.append(h3);
	h3.html('Choose Type of Data');
	var input = $('<input>');
	input.attr({'type': 'hidden',
		'name': 'action',
		'value': 'put'
	});
	div.append(input);
	var namedDataset_div = $('<div>');
	div.append(namedDataset_div);
	namedDataset_div.attr({'id': 'namedDataset'});
	namedDataset_div.css({'display': 'block'});
	var label = $('<label>');
	namedDataset_div.append(label);
	label.html('Enter a name for the dataset:');
	input = $('<input>');
	input.attr({'name': 'name',
		'type': 'text',
		'id': 'datasetName'
	});
	namedDataset_div.append(input);
	label = $('<label>');
	div.append(label);
	label.html('Select a type of dataset definition:');
	var select = $('<select>');
	div.append(select);
	select.attr({'name': 'type',
		'id': 'type',
		'onchange': "changeNameFormType('create', '');"
	});
	var option = $('<option>');
	select.append(option);
	option.text('blank (Dataset node for metadata-only)');
	option.attr('value', 'blank');
	option = $('<option>');
	select.append(option);
	option.text('file (Named dataset for locally stored file)');
	option.attr({'value': 'file',
		'selected': 'selected'});
	option = $('<option>');
	select.append(option);
	option.text('url (Named dataset for URL redirecting)');
	option.attr({'value': 'url'});
	input = $('<input>');
	input.attr({'name': 'myfile',
		'type': 'file',
		'id': 'fileName'
	});
	input.css({'display': 'inline'});
	div.append(input);
	div.append($('<br>'));
	label = $('<label>');
	div.append(label);
	label.html('Select an initial read permission:');
	select = $('<select>');
	div.append(select);
	select.attr({'name': 'read users',
		'id': 'read users'
	});
	option = $('<option>');
	select.append(option);
	option.text('Only owner may read');
	option.attr('value', 'owner');
	option = $('<option>');
	select.append(option);
	option.text('Anybody may read');
	option.attr({'value': '*'});
	div.append($('<br>'));
	label = $('<label>');
	div.append(label);
	label.html('Select an initial write permission:');
	select = $('<select>');
	div.append(select);
	select.attr({'name': 'write users',
		'id': 'write users'
	});
	option = $('<option>');
	select.append(option);
	option.text('Only owner may write');
	option.attr('value', 'owner');
	option = $('<option>');
	select.append(option);
	option.text('Anybody may write');
	option.attr({'value': '*'});
	div.append($('<br>'));
	label = $('<label>');
	div.append(label);
	label.html('Default View:');
	select = $('<select>');
	div.append(select);
	select.attr({'name': 'defaultView',
		'id': 'defaultView',
		'typestr': 'view',
		'onclick': "chooseOptions('" + HOME + "', '" + WEBAUTHNHOME + "', 'view', 'defaultView')"
	});
	option = $('<option>');
	select.append(option);
	option.text('Choose a View name');
	option.attr('value', '');
	div.append($('<br>'));
	label = $('<label>');
	div.append(label);
	label.html('Status of the dataset:  ');
	input = $('<input>');
	input.attr({'type': 'checkbox',
		'id': 'incomplete',
		'name': 'incomplete',
		'value': 'incomplete',
		'checked': 'checked'
	});
	div.append(input);
	label = $('<label>');
	div.append(label);
	label.html('Incomplete');
	input = $('<input>');
	input.attr({'type': 'submit',
		'id': 'submit',
		'value': 'Submit'
	});
	form.append(input);
	div = $('<div>');
	uiDiv.append(div);
	div.attr({'id': 'Copy'})
}

function showFileLink(predicate, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/query/' + predicate + '(url;tagdef)';
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postShowFileLink(data[0]);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){showFileLink(predicate, count)}, delay);
			}
		}
	});
}

function postShowFileLink(data) {
	var url = data['url'];
	var tagdef = data['tagdef'];
	if (url == null) {
		alert('NULL url');
	} else {
		var index = url.indexOf('/query/');
		if (index == -1) {
			alert('url "' + url + '" is not a query.');
		} else {
			index += '/query/'.length;
			viewLink(url.substr(index));
		}
	}
}

function getTagDefinition(predicate, view, count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/session'
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			var uiDiv = $('#ui');
			uiDiv.html('');
			USER_ROLES = data['attributes'];
			USER = data['client'];
			tagsUI(predicate, view, data['attributes']);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){getTagDefinition(predicate, view, count)}, delay);
			}
		}
	});
}

function uploadStudy(count) {
	if (count == null) {
		count = 0;
	}
	var url = HOME + '/study?action=upload'
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postUploadStudy(data);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){uploadStudy(count)}, delay);
			}
		}
	});
}

function downloadStudy(url, count) {
	if (count == null) {
		count = 0;
	}
	$.ajax({
		url: HOME + '/' + url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postDownloadStudy(data);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){downloadStudy(url, count)}, delay);
			}
		}
	});
}

function postUploadStudy(data) {
	var params = data.params;
	var div1 = $('<div>');
	var h3 = $('<h3>');
	div1.append(h3);
	h3.html('Status');
	var table = $('<table>');
	div1.append(table);
	var tr = $('<tr>');
	table.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.addClass('applet');
	var applet = $('<applet>');
	applet.attr({'NAME': 'TagFileUploader',
		'CODE': 'edu.isi.misd.tagfiler.TagFilerUploadApplet',
		'CODEBASE': '/tagfiler/static',
		 'ARCHIVE': 'isi-misd-tagfiler-upload.jar,apache-mime4j-0.6.jar,commons-codec-1.4.jar,commons-logging-1.1.1.jar,httpclient-4.0.3.jar,httpcore-4.0.1.jar,httpmime-4.0.3.jar,jakarta-commons-httpclient-3.1.jar,jsse.jar,plugin.jar,json-org.jar',
		 'width': 25,
		 'height': 25,
		 'MAYSCRIPT': 'true'
	});
	var param;
	if (params['tagfiler.cookie.name'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.cookie.name',
			'value': params['tagfiler.cookie.name']});
	}
	if (params['tagfiler.server.url'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.server.url',
			'value': params['tagfiler.server.url']});
	}
	param = $('<param>');
	applet.append(param);
	param.attr({'name': 'classloader_cache',
		'value': 'false'});
	param = $('<param>');
	applet.append(param);
	param.attr({'name': 'separate_jvm',
		'value': 'true'});
	if (params['tagfiler.applet.test'] != null && params['tagfiler.applet.test'].length > 0) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.applet.test',
			'value': '' + params['tagfiler.applet.test']});
	}
	if (params['tagfiler.applet.log'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.applet.log',
			'value': params['tagfiler.applet.log']});
	}
	if (params['custom.properties'] != null && params['custom.properties'].length > 0) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'custom.properties',
			'value': '' + params['custom.properties']});
	}
	if (params['tagfiler.connections'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.connections',
			'value': '' + params['tagfiler.connections']});
	}
	if (params['tagfiler.allow.chunks'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.allow.chunks',
			'value': '' + params['tagfiler.allow.chunks']});
	}
	if (params['tagfiler.socket.buffer.size'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.socket.buffer.size',
			'value': '' + params['tagfiler.socket.buffer.size']});
	}
	if (params['tagfiler.chunkbytes'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.chunkbytes',
			'value': '' + params['tagfiler.chunkbytes']});
	}
	if (params['tagfiler.client.socket.timeout'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.client.socket.timeout',
			'value': '' + params['tagfiler.client.socket.timeout']});
	}
	if (params['tagfiler.retries'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.retries',
			'value': '' + params['tagfiler.retries']});
	}
	var hr = $('<hr>');
	var b = $('<b>');
	b.html('You must have Java-enabled browser (JRE 1.5+) to run the TagFiler Applet. Download JRE 1.5 for your system from the following link:');
	var a = $('<a>');
	a.attr({'href': 'http://www.java.com/en/download/manual.jsp'});
	a.html('http://www.java.com/en/download/manual.jsp');
	hr.append(b);
	hr.append('<br>');
	hr.append(a);
	hr.append('<br>');
	applet.append(hr);
	td.append(applet);
	td = $('<td>');
	tr.append(td);
	table = $('<table>');
	td.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.addClass('status-wrapper');
	td.attr({'id': 'Status'});
	b = $('<b>');
	td.append(b);
	b.html('Select a directory to upload');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	table = $('<table>');
	td.append(table);
	table.addClass('table-border');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.attr({'id': 'ProgressBar'});
	var tempString = '';
	for (var i=0; i < 60; i++) {
		tempString += '&nbsp;'
	}
	td.html(tempString);
	var div1_2 = $('<div>');
	h3 = $('<h3>');
	div1_2.append(h3);
	h3.html('Dataset Name');
	table = $('<table>');
	div1_2.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	var input = $('<input>');
	input.attr({'id': 'TransmissionNumber',
		'name': 'TransmissionNumber',
		'type': 'text',
		'value': '',
		'disabled': 'disabled'});
	td.append(input);
	td = $('<td>');
	tr.append(td);
	input = $('<input>');
	input.attr({'name': 'DatasetName',
		'id': 'DatasetName Automatically',
		'type': 'radio',
		'value': 'automatically',
		'checked': 'checked',
		'onclick': 'resetDatasetName()'});
	td.append(input);
	var label = $('<label>');
	td.append(label);
	label.html('Generate Automatically');
	td.append($('<br>'));
	input = $('<input>');
	input.attr({'name': 'DatasetName',
		'id': 'DatasetName Set',
		'type': 'radio',
		'value': 'set',
		'onclick': 'setDatasetName()'});
	td.append(input);
	label = $('<label>');
	td.append(label);
	label.html('Set');
	var div2 = $('<div>');
	h3 = $('<h3>');
	div2.append(h3);
	h3.html('Source Directory for Upload');
	table = $('<table>');
	div2.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.addClass('directory');
	td.attr({'id': 'DestinationDirectory'});
	var tempString = '';
	for (var i=0; i < 60; i++) {
		tempString += '&nbsp;'
	}
	td.html(tempString);
	td = $('<td>');
	tr.append(td);
	var button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Browse', 
		'id': 'Browse',
		'value': '',
		'disabled': 'disabled',
		'onclick': 'uploadBrowse()'});
	button.html('Browse');
	td.append(button);
	var div3 = $('<div>');
	h3 = $('<h3>');
	div3.append(h3);
	h3.html('Checksum');
	var input = $('<input>');
	input.attr({'type': 'checkbox',
		'id': 'cksum',
		'name': 'cksum',
		'value': 'on',
		'checked': 'checked'});
	div3.append(input);
	var label = $('<label>');
	div3.append(label);
	label.html('Set');
	var div4 = $('<div>');
	h3 = $('<h3>');
	div4.append(h3);
	h3.html('Submit');
	button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Upload All',
		'id': 'Upload All',
		'disabled': 'disabled',
		'onclick': "uploadAll('all')"});
	button.html('Upload All');
	div4.append(button);
	button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Resume',
		'id': 'Resume',
		'onclick': "uploadAll('resume')"});
	button.css({'visibility': 'hidden'});
	button.html('Resume');
	div4.append(button);
	var div5 = $('<div>');
	h3 = $('<h3>');
	div5.append(h3);
	h3.html('Study Tags');
	table = $('<table>');
	div5.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	var div = $('<div>');
	td.append(div);
	div.attr({'id': 'custom-tags'});
	table = $('<table>');
	div.append(table);
	table.attr({id: 'Required Tags'});
	table.addClass('table-wrapper');
	var appletTagnames = data['appletTagnames'];
	var appletTagnamesRequire = data['appletTagnamesRequire'];
	for (var i=0; i < appletTagnames.length; i++) {
		var trTag = $('<tr>');
		table.append(trTag);
		var tdTag = $('<td>');
		trTag.append(tdTag);
		tdTag.addClass('tag-name');
		tdTag.html(appletTagnames[i]);
		tdTag = $('<td>');
		trTag.append(tdTag);
		var inputTag = $('<input>');
		inputTag.attr({'type': 'text',
			'name': appletTagnames[i],
			'id': appletTagnames[i]+'_id'
		});
		if (appletTagnamesRequire.contains(appletTagnames[i])) {
			inputTag.attr('required', 'required');
		}
		tdTag.append(inputTag);
	}

	var div6 = $('<div>');
	h3 = $('<h3>');
	div6.append(h3);
	h3.html('File(s) that will be uploaded');
	table = $('<table>');
	div6.append(table);
	table.addClass('file-list');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.attr({'id': 'Files'});
	td.addClass('text-tree');
	tempString = '';
	for (var i=0; i < 60; i++) {
		tempString += '&nbsp;'
	}
	td.html(tempString);
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Study Upload');
	uiDiv.append(div1);
	uiDiv.append(div1_2);
	uiDiv.append(div2);
	uiDiv.append(div3);
	uiDiv.append(div4);
	uiDiv.append(div5);
	uiDiv.append(div6);
}

function postDownloadStudy(data) {
	var params = data.params;
	var div1 = $('<div>');
	var h3 = $('<h3>');
	div1.append(h3);
	h3.html('Status');
	var table = $('<table>');
	div1.append(table);
	var tr = $('<tr>');
	table.append(tr);
	var td = $('<td>');
	tr.append(td);
	td.addClass('applet');
	var applet = $('<applet>');
	applet.attr({'NAME': 'TagFileDownloader',
		'CODE': 'edu.isi.misd.tagfiler.TagFilerDownloadApplet',
		'CODEBASE': '/tagfiler/static',
		 'ARCHIVE': 'isi-misd-tagfiler-upload.jar,apache-mime4j-0.6.jar,commons-codec-1.4.jar,commons-logging-1.1.1.jar,httpclient-4.0.3.jar,httpcore-4.0.1.jar,httpmime-4.0.3.jar,jakarta-commons-httpclient-3.1.jar,jsse.jar,plugin.jar,json-org.jar',
		 'width': 25,
		 'height': 25,
		 'MAYSCRIPT': 'true'
	});
	var param;
	if (params['tagfiler.cookie.name'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.cookie.name',
			'value': params['tagfiler.cookie.name']});
	}
	if (params['tagfiler.server.url'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.server.url',
			'value': params['tagfiler.server.url']});
	}
	if (params['tagfiler.server.transmissionnum'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.server.transmissionnum',
			'value': params['tagfiler.server.transmissionnum']});
	}
	if (params['tagfiler.server.version'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.server.version',
			'value': params['tagfiler.server.version']});
	}
	param = $('<param>');
	applet.append(param);
	param.attr({'name': 'classloader_cache',
		'value': 'false'});
	param = $('<param>');
	applet.append(param);
	param.attr({'name': 'separate_jvm',
		'value': 'true'});
	if (params['tagfiler.applet.test'] != null && params['tagfiler.applet.test'].length > 0) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.applet.test',
			'value': '' + params['tagfiler.applet.test']});
	}
	if (params['tagfiler.applet.log'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.applet.log',
			'value': params['tagfiler.applet.log']});
	}
	if (params['custom.properties'] != null && params['custom.properties'].length > 0) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'custom.properties',
			'value': '' + params['custom.properties']});
	}
	if (params['tagfiler.connections'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.connections',
			'value': '' + params['tagfiler.connections']});
	}
	if (params['tagfiler.allow.chunks'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.allow.chunks',
			'value': '' + params['tagfiler.allow.chunks']});
	}
	if (params['tagfiler.socket.buffer.size'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.socket.buffer.size',
			'value': '' + params['tagfiler.socket.buffer.size']});
	}
	if (params['tagfiler.chunkbytes'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.chunkbytes',
			'value': '' + params['tagfiler.chunkbytes']});
	}
	if (params['tagfiler.client.socket.timeout'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.client.socket.timeout',
			'value': '' + params['tagfiler.client.socket.timeout']});
	}
	if (params['tagfiler.retries'] != null) {
		param = $('<param>');
		applet.append(param);
		param.attr({'name': 'tagfiler.retries',
			'value': '' + params['tagfiler.retries']});
	}
	var hr = $('<hr>');
	var b = $('<b>');
	b.html('You must have Java-enabled browser (JRE 1.5+) to run the TagFiler Applet. Download JRE 1.5 for your system from the following link:');
	var a = $('<a>');
	a.attr({'href': 'http://www.java.com/en/download/manual.jsp'});
	a.html('http://www.java.com/en/download/manual.jsp');
	hr.append(b);
	hr.append('<br>');
	hr.append(a);
	hr.append('<br>');
	applet.append(hr);
	td.append(applet);
	td = $('<td>');
	tr.append(td);
	table = $('<table>');
	td.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.addClass('status-wrapper');
	td.attr({'id': 'Status'});
	b = $('<b>');
	td.append(b);
	b.html('Click "Update" to fill the form');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	table = $('<table>');
	td.append(table);
	table.addClass('table-border');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.attr({'id': 'ProgressBar'});
	var tempString = '';
	for (var i=0; i < 60; i++) {
		tempString += '&nbsp;'
	}
	td.html(tempString);
	var div1_2 = $('<div>');
	h3 = $('<h3>');
	div1_2.append(h3);
	h3.html('Dataset');
	table = $('<table>');
	div1_2.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	var table = $('<table>');
	td.append(table);
	table.addClass('table-wrapper');
	table.attr({'rules': 'all'})
	var tr1 = $('<tr>');
	table.append(tr1);
	td = $('<td>');
	tr1.append(td);
	td.addClass('tag-name');
	td.html('Name');
	td = $('<td>');
	tr1.append(td);
	var input = $('<input>');
	input.attr({'id': 'TransmissionNumber',
		'name': 'TransmissionNumber',
		'type': 'text',
		'value': '',
		'disabled': 'disabled'});
	td.append(input);
	tr1 = $('<tr>');
	table.append(tr1);
	td = $('<td>');
	tr1.append(td);
	td.addClass('tag-name');
	td.html('Version');
	td = $('<td>');
	tr1.append(td);
	input = $('<input>');
	input.attr({'id': 'Version',
		'type': 'text',
		'value': '',
		'disabled': 'disabled'});
	td.append(input);
	td = $('<td>');
	tr.append(td);
	var button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Update', 
		'id': 'UpdateButton',
		'value': '',
		'disabled': 'disabled',
		'onclick': 'getDatasetInfo()'});
	button.html('Update');
	td.append(button);
	var div2 = $('<div>');
	h3 = $('<h3>');
	div2.append(h3);
	h3.html('Destination Directory for Download');
	table = $('<table>');
	div2.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.addClass('directory');
	td.attr({'id': 'DestinationDirectory'});
	var tempString = '';
	for (var i=0; i < 80; i++) {
		tempString += '&nbsp;'
	}
	td.html(tempString);
	td = $('<td>');
	tr.append(td);
	var button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Browse', 
		'id': 'Browse',
		'value': '',
		'disabled': 'disabled',
		'onclick': 'downloadBrowse()'});
	button.html('Browse');
	td.append(button);
	var div3 = $('<div>');
	h3 = $('<h3>');
	div3.append(h3);
	h3.html('Checksum');
	var input = $('<input>');
	input.attr({'type': 'checkbox',
		'id': 'cksum',
		'name': 'cksum',
		'value': 'on',
		'checked': 'checked'});
	div3.append(input);
	var label = $('<label>');
	div3.append(label);
	label.html('Verify');
	var div4 = $('<div>');
	h3 = $('<h3>');
	div4.append(h3);
	h3.html('Submit');
	button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Download Files',
		'id': 'Download Files',
		'disabled': 'disabled',
		'onclick': "downloadFiles('all')"});
	button.html('Download Files');
	div4.append(button);
	button = $('<button>');
	button.attr({'type': 'button',
		'name': 'Resume',
		'id': 'Resume',
		'onclick': "downloadFiles('resume')"});
	button.css({'visibility': 'hidden'});
	button.html('Resume');
	div4.append(button);
	var div5 = $('<div>');
	h3 = $('<h3>');
	div5.append(h3);
	h3.html('Study Tags');
	table = $('<table>');
	div5.append(table);
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	var div = $('<div>');
	td.append(div);
	div.attr({'id': 'Required Tags'});
	table = $('<table>');
	div.append(table);
	table.attr({id: 'Dataset Tags',
		'rules': 'all'});
	table.addClass('table-wrapper');
	var div6 = $('<div>');
	h3 = $('<h3>');
	div6.append(h3);
	h3.html('File(s) that will be downloaded');
	table = $('<table>');
	div6.append(table);
	table.addClass('file-list');
	tr = $('<tr>');
	table.append(tr);
	td = $('<td>');
	tr.append(td);
	td.attr({'id': 'Files'});
	td.addClass('text-tree');
	tempString = '';
	for (var i=0; i < 70; i++) {
		tempString += '&nbsp;'
	}
	td.html(tempString);
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Study Download');
	uiDiv.append(div1);
	uiDiv.append(div1_2);
	uiDiv.append(div2);
	uiDiv.append(div3);
	uiDiv.append(div4);
	uiDiv.append(div5);
	uiDiv.append(div6);
}

function redirectApplet(url) {
	var index = url.indexOf('/appleterror');
	if (index != -1) {
		var status = 'An unknown error prevented the applet from functioning.';
		index = url.indexOf('/appleterror?status=');
		if (index != -1) {
			var err = url.substr(index + '/appleterror?status='.length);
			if (err.length > 0) {
				status = decodeURIComponent(err.replace(/\+/g, '%20'));
			}
		}
		var uiDiv = $('#ui');
		uiDiv.html('');
		var h1 = $('<h1>');
		uiDiv.append(h1);
		h1.html('Applet Failed');
		uiDiv.append($('<p>'));
		var div = $('<div>');
		uiDiv.append(div);
		div.addClass('error');
		div.html(status);
		var p = $('<p>');
		uiDiv.append(p);
		p.html('If you plan to request help, please note the current time as well as ' +
				'any other information you can remember about steps that preceded this error.');
	} else {
		getAppletTreeStatus(url);
	}
}

function getAppletTreeStatus(url, count) {
	if (count == null) {
		count = 0;
	}
	$.ajax({
		url: url,
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
		accepts: {text: 'application/json'},
		dataType: 'json',
 		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postGetAppletTreeStatus(data);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){getAppletTreeStatus(url, count)}, delay);
			}
		}
	});
	
}

function postGetAppletTreeStatus(data) {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var params = data.params;
	var odd = true;
	var classname = 'transmissionnum';
	if (params['success'] != null) {
		var h2 = $('<h2>');
		uiDiv.append(h2);
		h2.html('Completed');
		uiDiv.append($('<p>'));
		var b = $('<b>');
		uiDiv.append(b);
		b.html(params['success']);
		uiDiv.append($('<p>'));
		var label = $('<label>');
		uiDiv.append(label);
		label.html('See below for a summary of the study.');
	} else if (params['error'] != null) {
		classname = 'error';
		var h2 = $('<h2>');
		uiDiv.append(h2);
		h2.html('Failed');
		var div = $('<div>');
		uiDiv.append(div);
		div.addClass(classname);
		div.html(params['error']);
	} else {
		var h2 = $('<h2>');
		uiDiv.append(h2);
		h2.html('Status');
		var label = $('<label>');
		uiDiv.append(label);
		label.html('The status of the transfer is unknown.');
	}
	if (params['name'] != null) {
		uiDiv.append($('<p>'));
		var div = $('<div>');
		uiDiv.append(div);
		div.addClass(classname);
		div.html('Dataset Name: ' + params['name']);
		if (params['version'] != null) {
			uiDiv.append($('<p>'));
			var div = $('<div>');
			uiDiv.append(div);
			div.addClass(classname);
			div.html('Dataset Version: ' + params['version']);
		}
		if (params['direction'] == 'upload' && params['success'] != null) {
			uiDiv.append($('<p>'));
			var label = $('<label>');
			uiDiv.append(label);
			label.html('Please write this Dataset Name on the visit inventory form.');
		}
	}
	uiDiv.append($('<p>'));
	var table = $('<table>');
	uiDiv.append(table);
	table.addClass('file-tag-list');
	for (var i=0; i < params['appletTagvals'].length; i++) {
		var tr = $('<tr>');
		table.append(tr);
		tr.addClass(odd ? 'file-tag odd' : 'file-tag even');
		odd = !odd;
		var arr = params['appletTagvals'][i];
		var tag = arr[0];
		var vals = arr[1];
		var th = $('<th>');
		tr.append(th);
		th.addClass('file-tag');
		th.addClass(idquote(tag));
		th.html(tag);
		var td = $('<td>');
		tr.append(td);
		td.addClass('file-tag');
		td.addClass(idquote(tag));
		for (var j=0; j < vals.length; j++) {
			if (j != 0) {
				td.append($('<br>'));
			}
			var label = $('<label>');
			td.append(label);
			label.html(vals[j]);
		}
	}
	if (params['direction'] == 'upload') {
		uiDiv.append($('<p>'));
		var label = $('<label>');
		uiDiv.append(label);
		label.html('Please compare this study information with that on the visit inventory form.');
	}
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Study Files');
	var ul = $('<ul>');
	uiDiv.append(ul);
	for (var i=0; i < params['files'].length; i++) {
		var li = $('<li>');
		ul.append(li);
		var index = params['files'][i].indexOf('@');
		li.html(index == -1 ? params['files'][i] : params['files'][i].substr(0, index))
	}
}


/**
 * Converts a value to a JSON string representation
 * 
 * @param val
 * 	the value to converted
 * @return the JSON string representation
 */
function valueToString(val) {
	if ($.isArray(val)) {
		return arrayToString(val);
	} else if ($.isPlainObject(val)) {
		return objectToString(val);
	} else if ($.isNumeric(val)) {
		return val;
	} else if ($.isEmptyObject(val)) {
		return '"EmptyObject"';
	} else if ($.isFunction(val)) {
		return '"Function"';
	} else if($.isWindow(val)) {
		return '"Window"';
	} else if ($.isXMLDoc(val)) {
		return '"XMLDoc"';
	} else {
		var valType = $.type(val);
		if (valType == 'string') {
			return '"' + escapeDoubleQuotes(val) + '"';
		} else if (valType == 'object') {
			return '"Object"';
		} else {
			return '"' + valType + '"';
		}
	}
}

/**
 * Converts an object to a JSON string representation
 * 
 * @param obj
 * 	the object to converted
 * @return the JSON string representation
 */
function objectToString(obj) {
	var s = '{';
	var first = true;
	$.each(obj, function(key, val) {
		if (!first) {
			s += ',';
		}
		first = false;
		s += '"' + key + '":' + valueToString(val);
	});
	s += '}';
	return s;
}

/**
 * Converts an array to a JSON string representation
 * 
 * @param obj
 * 	the array to converted
 * @return the JSON string representation
 */
function arrayToString(obj) {
	var s = '[';
	var first = true;
	$.each(obj, function(i, val) {
		if (!first) {
			s += ',';
		}
		first = false;
		s += valueToString(val);
	});
	s += ']';
	return s;
}

/**
 * Method "escape" for a string
 * escape all the " characters 
 * 
 * @param text
 * 	the string to be escaped
 * @return the escaped string
 */
function escapeDoubleQuotes(text) {
	return text.replace(/"/g, '\\"');
}

function manageUserRoles(user) {
	var users = new Array();
	users.push(user);
	manageAllUsersAttributes(users);
}

function manageAllUsersAttributes(users, count) {
	if (count == null) {
		count = 0;
	}
	// get all the available attributes
	var url = HOME + '/attribute';
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: true,
  		timeout: AJAX_TIMEOUT,
		success: function(data, textStatus, jqXHR) {
			postManageAllUsersAttributes(data, users);
		},
		error: function(jqXHR, textStatus, errorThrown) {
			var retry = handleError(jqXHR, textStatus, errorThrown, ++count, url);
			if (retry && count <= MAX_RETRIES) {
				var delay = Math.round(Math.ceil((0.75 + Math.random() * 0.5) * Math.pow(10, count) * 0.00001));
				setTimeout(function(){manageAllUsersAttributes(users, count)}, delay);
			}
		}
	});
}

function postManageAllUsersAttributes(allAttributes, users) {
	var uiDiv = $('#ui');
	uiDiv.html('');
	var h2 = $('<h2>');
	uiDiv.append(h2);
	h2.html('Attribute Assignment Management');
	users.sort(compareIgnoreCase);
	allAttributes.sort(compareIgnoreCase);
	$.each(users, function(i, user) {
		var fieldset = $('<fieldset>');
		uiDiv.append(fieldset);
		fieldset.attr({'id': 'fieldset_' + idquote(user)});
		var legend = $('<legend>');
		fieldset.append(legend);
		legend.html('User "' + user + '"');
	});
	$.each(users, function(i, user) {
		manageMembership(allAttributes, user);
	});
}

