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
    cookie = null;
    for (c=0; c<cookies.length; c++) {
	kv = cookies[c].split("=");
	if (kv[0] == name) {
	    //log ('getCookie: found ' + kv[1]);
	    cookie = unescape(kv[1]);
	}
    }
    return cookie;
}

function setCookie(name, val) {
    val = encodeURIComponent(unescape(val));
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
    document.getElementById("Files").innerHTML = files;
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
function uploadAll() {
	if (validateUpload()) {
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
 * Enable setting a dataset name
 */
function setDatasetName() {
	document.getElementById('TransmissionNumber').disabled = false;
}

/**
 * Disable setting a dataset name
 */
function resetDatasetName() {
	var elem = document.getElementById('TransmissionNumber');
	elem.disabled = true;
	elem.value = "";
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
 * Enables/Disables the "Create Saved Query" button based on the query name value
 */
function checkQueryName() {
	if (document.getElementById('SavedQueryName').value.replace(/^\s*/, "").replace(/\s*$/, "").length > 0) {
    	document.getElementById('SavedQueryButton').disabled = false;
	} else {
    	document.getElementById('SavedQueryButton').disabled = true;
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
var width = 0;
var hasSize = false;

if(window.ActiveXObject) {
  ajax_request = new ActiveXObject("Microsoft.XMLHTTP");
}
else if(window.XMLHttpRequest) {
  ajax_request = new XMLHttpRequest();
}

if(ajax_request) {
  ajax_request.onreadystatechange = processSessionRequest;
}

var redirectToLogin = false;

function renderTagdefs(table) {
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
	    typedescs = JSON.parse(unescape(headers[i].innerHTML));
	    headers[i].innerHTML = "Tag type";
	}
	else {
	    labels = { "Tag name" : "Tag name",
		       "Owner" : "Owner",
		       "multivalue" : "#&nbsp;Values",
		       "readpolicy" : "Tag readers",
		       "writepolicy" : "Tag writers" };
	    headers[i].innerHTML = labels[headers[i].innerHTML];
	}
    }

    for (i=1; i<rows.length; i++) {
	if (rows[i].getAttribute("class") == "tagdef") {
	    if ( i % 2 == 1 ) {
		rows[i].className = "tagdef odd";
	    }
	    else {
		rows[i].className = "tagdef even";
	    }
	    var cells = rows[i].children;
	    var namecell = cells[columnmap["tagname"]];
	    var tagname = namecell.innerHTML;
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
			   "file" : "users who can access the file", 
			   "fowner" : "user who owns the file",
			   "tag" : (ownerand + "users in ACL") };
	    var readpolcell = cells[columnmap["readpolicy"]];
	    readpolcell.innerHTML = policy[readpolcell.innerHTML];
	    var writepolcell = cells[columnmap["writepolicy"]];
	    writepolcell.innerHTML = policy[writepolcell.innerHTML];

	    namecell.innerHTML = "<form "
		+ "encoding=\"application/x-www-url-encoded\" "
		+ "action=\"/tagfiler/tagdef\" method=\"post\">"
		+ "<input type=\"hidden\" name=\"tag\" value=\"" + tagname + "\" />"
		+ "<input type=\"hidden\" name=\"action\" value=\"delete\" />"
		+ "<input type=\"submit\" value=\"[X]\" title=\"delete " + tagname + "\" />"
		+ tagname + "</form>";
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

