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

var tagsArray = new Array();
tagsArray['Experiment'] = 'experimentID	principal	lab	start	mice	observations'.split('\t');
tagsArray['Lab'] = 'labID	site'.split('\t');
tagsArray['Mouse'] = 'mouseID	dob	dos	litter	cage	start age	mouse strain	lot#	supplier	treatment	samples	observations	cancer type	start	performer	#cells	weight'.split('\t');
tagsArray['Observation'] = 'observationID	start	weight	performer	samples'.split('\t');
tagsArray['Researcher'] = 'researcherID	email	lab'.split('\t');
tagsArray['Sample'] = 'sampleID	start	performer	freezer	shelf	sample type	serum sample type	observations'.split('\t');
tagsArray['Site'] = 'siteID	address'.split('\t');
tagsArray['Supplier'] = 'supplierID	address	email'.split('\t');
tagsArray['Treatment'] = 'treatmentID	drug	dose	lot#	performer'.split('\t');

var selectArray = 'lab	researcher	site	supplier	treatment'.split('\t');
var sharedId = new Array();
sharedId['researcher'] = 'performer	principal'.split('\t');

var enumArray = new Array();
enumArray['mouse strain'] = 'C57 black 6	nude	skid	other strain'.split('\t').sort();
enumArray['sample type'] = 'serum	tumor	spleen	other sample'.split('\t').sort();
enumArray['cancer type'] = 'lymphoma	prostate	breast	naive'.split('\t').sort();
enumArray['serum sample type'] = 'terminal bleed	other'.split('\t').sort();

var linkArray = new Array();
linkArray['mice'] = new Array();
linkArray['samples'] = new Array();
linkArray['observations'] = new Array();

var tagMapArray = new Array();
tagMapArray['mice'] = 'Mouse';
tagMapArray['samples'] = 'Sample';
tagMapArray['observations'] = 'Observation';

var dateArray = 'dob	dos	start'.split('\t');

var subjectArray = new Array();
var multivalueArray = 'address	email	mice	observations	samples'.split('\t');
var multivalueSelectArray = 'mice	observations	samples'.split('\t');

var groupTags = 'Experiment	Lab	Mouse	Observation	Researcher	Sample	Site	Supplier	Treatment'.split('\t').sort();

var groupCounter = new Array();
var groupName = new Array();
var groupType = new Array();

var selectedTags = new Array();

var multivalueIds = new Array();

var firstSubject;

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
		elem.setAttribute(arguments[i], arguments[i+1]);
	}
}

function getLeftOffset(id) {
	var elem = document.getElementById(id);
	var offset = elem.offsetLeft;
	var parent = elem.offsetParent;
	while (parent != null) {
		if (parent.offsetLeft != null) {
			offset += parent.offsetLeft;
		}
		parent = parent.offsetParent;
	}
	return offset;
}

function getTopOffset(id) {
	var elem = document.getElementById(id);
	var offset = elem.offsetTop;
	var parent = elem.offsetParent;
	while (parent != null) {
		if (parent.offsetTop != null) {
			offset += parent.offsetTop;
		}
		parent = parent.offsetParent;
	}
	return offset;
}

function deleteElementById(id) {
	var elem = document.getElementById(id);
	elem.parentNode.removeChild(elem);
}

function deleteElement(elem) {
	elem.parentNode.removeChild(elem);
}

function deleteColumn(id) {
	var row = document.getElementById(id).parentNode;
	var table = row.parentNode;
	var index = 0;
	var columns = row.children;
	for (var i=0; i < columns.length; i++) {
		if (columns[i].getAttribute('id') == id) {
			index = i;
			break;
		}
	}
	var rows = table.children;
	for (var i=0; i < rows.length; i++) {
		var column = rows[i].children[index];
		rows[i].removeChild(column);
	}
}

function getColumnIndex(id) {
	var row = document.getElementById(id).parentNode;
	var columns = row.children;
	var index = -1;
	for (var i=0; i < columns.length; i++) {
		if (columns[i].getAttribute('id') == id) {
			index = i;
			break;
		}
	}
	return index;
}

function getVisibleColumn(group) {
	var id = makeId('subjects', group);
	var row = document.getElementById(id).parentNode;
	var position = -1;
	var columns = row.children;
	for (var i=1; i < columns.length; i++) {
		if (columns[i].style.display.length == 0) {
			position = i;
			break;
		}
	}
	return position;
}

function getHideColumn(group) {
	var id = makeId('subjects', group);
	var row = document.getElementById(id).parentNode;
	var position = -1;
	var columns = row.children;
	for (var i=1; i < columns.length; i++) {
		if (columns[i].style.display.length > 0) {
			position = i;
			break;
		}
	}
	return position;
}

function getVisibleColumnCount(group) {
	var id = makeId('subjects', group);
	var row = document.getElementById(id).parentNode;
	var total = 0;
	var columns = row.children;
	for (var i=1; i < columns.length; i++) {
		if (columns[i].style.display.length == 0) {
			total++;
		}
	}
	return total;
}

function hideColumn(group, position) {
	var id = makeId('subjects', group);
	var table = document.getElementById(id).parentNode.parentNode;
	var rows = table.children;
	for (var i=0; i < rows.length; i++) {
		rows[i].children[position].style.display = 'none';
	}
}

function displayColumn(group, position) {
	var id = makeId('subjects', group);
	var table = document.getElementById(id).parentNode.parentNode;
	var rows = table.children;
	for (var i=0; i < rows.length; i++) {
		rows[i].children[position].style.display = '';
	}
}

function displayCollapseColumn(group) {
	while (true) {
		var position = getVisibleColumn(group);
		if (position == -1) {
			break;
		}
		hideColumn(group, position);
	}
	enableNavigationButtons(group);
}

function displayExpandColumn(group) {
	while (true) {
		var position = getHideColumn(group);
		if (position == -1) {
			break;
		}
		displayColumn(group, position);
	}
	enableNavigationButtons(group);
}

function showColumn(group, index) {
	var dt = document.getElementById(makeId('Subject', group, 'span'));
	if (dt.nextSibling.style.display == 'none') {
		var header = dt.getElementsByTagName('span')[0].children[0].children[0].children[1].innerHTML;
		tog(dt, header);
	}
	displayCollapseColumn(group);
	var id = makeId('Subject', group, index);
	var columnIndex = getColumnIndex(id);
	displayColumn(group, columnIndex);
	enableNavigationButtons(group);
}

function enableNavigationButtons(group) {
	var id = makeId('subjects', group);
	var expandId = makeId(id, 'Expand');
	var collapseId = makeId(id, 'Collapse');
	document.getElementById(expandId).style.display = 'none';
	document.getElementById(collapseId).style.display = 'none';

	var count = getVisibleColumnCount(group);
	var subjects = document.getElementById(id).parentNode.children.length-1;
	if (count > 0) {
		document.getElementById(collapseId).style.display = '';
	}
	if (count < subjects) {
		document.getElementById(expandId).style.display = '';
	}
}

function appendColumn(id, values) {
	var row = document.getElementById(id).parentNode;
	var table = row.parentNode;
	var rows = table.children;
	for (var i=0; i < rows.length; i++) {
		rows[i].appendChild(values[i]);
	}
}

function newTags(group, value) {
	var newTags = new Array();
	for (var i=0; i<tagsArray[value].length; i++) {
		if (!selectedTags[group-1].contains(tagsArray[value][i])) {
			selectedTags[group-1].push(tagsArray[value][i]);
			newTags.push(tagsArray[value][i]);
		}
	}
	var table = document.getElementById(makeId('subjects', group)).parentNode.parentNode;
	var rowClass = 'even';
	for (var i=0; i<newTags.length; i++) {
		var row = document.createElement('tr');
		makeAttributes(row,
					   'class', 'file-tag ' + rowClass);
		rowClass = (rowClass == 'odd') ? 'even' : 'odd';
		var td = document.createElement('td');
		makeAttributes(td,
					   'class', 'file-tag');
		td.innerHTML = newTags[i];
		row.appendChild(td);
		for (var j=1; j <= groupCounter[group-1]; j++) {
			var subjectId = makeId('Subject', group, j);
			if (document.getElementById(subjectId) == null) {
				// subject might have been deleted
				continue;
			}
			var id = makeId(subjectId, newTags[i]);
			var td = document.createElement('td');
			makeAttributes(td,
						   'nowrap', 'nowrap',
						   'id', id,
						   'class', 'file-tag');
			td.appendChild(tagCell(group, newTags[i], j));
			row.appendChild(td);
		}
		table.insertBefore(row, table.lastChild);
	}
	makeAttributes(table.lastChild,
				   'class', 'file-footer ' + rowClass);
}

function newSubject(group, inner) {
	var typeCode = groupType[group-1] + '-';
	if (inner == 'true') {
		typeCode = '-' + groupType[group-1] + '-';
	}
	var subjectsId = makeId('subjects', group);
	var suffix = document.getElementById(subjectsId).getAttribute('suffix');
	var values = new Array();
	var countIndex = groupCounter[group-1] + 1;
	var subjectId = makeId('Subject', group, countIndex);
	groupCounter[group-1] = countIndex;
	var th = document.createElement('th');
	makeAttributes(th,
				   'class', 'file-tag',
				   'id', makeId(subjectId, 'header'));
	th.innerHTML = (inner == 'false' ? USER + '-' : '') + groupName[group-1] + typeCode + countIndex + suffix;
	values.push(th);
	for (var i=0; i<selectedTags[group-1].length; i++) {
		var id = makeId(subjectId, selectedTags[group-1][i]);
		var td = document.createElement('td');
		makeAttributes(td,
					   'nowrap', 'nowrap',
					   'id', id,
					   'class', 'file-tag entity');
		td.appendChild(tagCell(group, selectedTags[group-1][i], countIndex));
		values.push(td);
	}
	var td = document.createElement('td');
	makeAttributes(td,
				   'id', subjectId,
				   'class', 'file-tag');
	var input = document.createElement('input');
	makeAttributes(input,
				   'type', 'button',
				   'onclick', makeFunction('hideSubject', group, countIndex),
				   'value', 'Hide ' + groupType[group-1]);
	td.appendChild(input);
	values.push(td);
	appendColumn(subjectsId, values);
	var id = makeId(subjectId, groupType[group-1].substr(0,1).toLowerCase() + groupType[group-1].substr(1) + 'ID');
	var subjectName = groupName[group-1] + typeCode + countIndex + suffix;
	var textValue = (inner == 'false' ? USER + '-' + subjectName : subjectName);
	document.getElementById(makeId(id, 'input')).value = textValue;
	makeAttributes(document.getElementById(makeId(id, 'input')),
				   'size', textValue.length);
	enableNavigationButtons(group);
	var headerId = makeId(subjectId, 'header');
	window.scrollTo(getLeftOffset(headerId), getTopOffset(headerId));
	return subjectName;
}

function deleteSubject(group, position) {
	var elemId = makeId('Subject', group, 'val', position);
	deleteElementById(elemId);
	var id = makeId('Subject', group, position);
	var count = getVisibleColumnCount(group);
	var index = getColumnIndex(id);
	var row = document.getElementById(id).parentNode;
	var length = row.children.length;
	deleteColumn(id);
	if (row.children.length == 1) {
		// the div that contains the table;
		id = makeId('Subject', group, 1, 'container');
		var div = document.getElementById(id);
		deleteElement(div);
	} else {
		enableNavigationButtons(group);
	}
}

function hideSubject(group, position) {
	var id = makeId('Subject', group, position);
	var index = getColumnIndex(id);
	hideColumn(group, index);
	enableNavigationButtons(group);
}

function selectTags() {
	var select_list_field = document.getElementById("tags");
	var select_list_selected_index = select_list_field.selectedIndex;
	var value = select_list_field.options[select_list_selected_index].value;
	var subjectGroupName;
	while (true) {
		subjectGroupName = prompt(value + ' name:');
		if (subjectGroupName == null) {
			// cancel
			document.getElementById('selectTag').selected = "selected";
			return;
		}
		subjectGroupName = subjectGroupName.replace(/^\s*/, "").replace(/\s*$/, "");
		if (subjectGroupName.length > 0) {
			break;
		} else {
			alert(value + ' name can not be empty.');
		}
	}
	selectSubject(value, subjectGroupName + '-', null, document.getElementById('all_subjects'), subjectGroupName);
	document.getElementById('selectTag').selected = "selected";
}

function tog(dt, header) {
	var dd = dt.nextSibling;
	var toOpen = (dd.style.display == 'none');
	dd.style.display = toOpen ? '' : 'none';
	dt.getElementsByTagName('span')[0].innerHTML = '';
	var spanTitle = document.createElement('table');
	dt.getElementsByTagName('span')[0].appendChild(spanTitle);
	var tr = document.createElement('tr');
	makeAttributes(tr,
				   'class', 'no-border');
	spanTitle.appendChild(tr);
	var td = document.createElement('td');
	tr.appendChild(td);
	var img = document.createElement('img');
	td.appendChild(img);
	makeAttributes(img,
				   'src', resourcePrefix + (toOpen ? 'minus.png' : 'plus.png'),
				   'width', '16',
				   'height', '16',
				   'border', '0',
				   'alt', (toOpen ? '-' : '+'));
	td = document.createElement('td');
	tr.appendChild(td);
	td.innerHTML = header;
}

function selectSubject(value, subjectGroupName, suffix, parent, header) {
	var inner = (subjectGroupName == header + '-') ? 'false' : 'true';
	var typeCode = value + '-';
	if (inner == 'true') {
		typeCode = '-' + value + '-';
	}
	if (suffix == null) {
		suffix = '';
	}
	suffix = suffix.replace(/^\s*/, "").replace(/\s*$/, "");
	if (suffix.length > 0) {
		suffix = '-' + suffix;
	}
	groupName[groupName.length] = subjectGroupName;
	firstSubject = 0;
	
	// check if we have already such subjects
	if (inner == 'false') {
		var PREFIX = HOME + '/query/';
		var LIKE = 'ID:like:';
		var SUFFIX = '?limit=none&versions=latest';
		var data_id = USER + '-' + subjectGroupName + value + '-' + '%';
		var url = PREFIX + value.substr(0,1).toLowerCase() + value.substr(1) + LIKE + encodeURIComponent(data_id) + SUFFIX;
		$.ajax({
			url: url,
			accepts: {text: 'text/uri-list'},
			dataType: 'text',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: false,
			success: handleSubjectResponse,
			error: handleError
		});
	}
	
	firstSubject += 1;
	selectedTags[selectedTags.length] = new Array();
	groupCounter[groupCounter.length] = firstSubject;
	groupType[groupType.length] = value;
	if (groupCounter.length == 1) {
		document.getElementById('all_subjects').style.display = 'block';
	}
	var index = groupCounter.length;

	var container = document.createElement('div');
	var subjectId = makeId('Subject', index);
	var subjectId1 = makeId(subjectId, firstSubject);
	var headerId = makeId(subjectId1, 'header');
	makeAttributes(container,
				   'id', makeId(subjectId1, 'container'));
	parent.appendChild(container);
	var dl = document.createElement('dl');
	container.appendChild(dl);
	var dt = document.createElement('dt');
	makeAttributes(dt,
				   'onclick', makeFunction('tog', 'this', str((inner == 'false' ? USER + '-' + header : header))),
				   'id', makeId(subjectId, 'span'));
	dl.appendChild(dt);
	var span = document.createElement('span');
	makeAttributes(span,
				   'style', 'color: blue; cursor: default');
	dt.appendChild(span);
	var spanTitle = document.createElement('table');
	span.appendChild(spanTitle);
	var tr = document.createElement('tr');
	makeAttributes(tr,
				   'class', 'no-border');
	spanTitle.appendChild(tr);
	var td = document.createElement('td');
	tr.appendChild(td);
	var img = document.createElement('img');
	td.appendChild(img);
	makeAttributes(img,
				   'src', resourcePrefix + 'minus.png',
				   'width', '16',
				   'height', '16',
				   'border', '0',
				   'alt', '-');
	td = document.createElement('td');
	tr.appendChild(td);
	td.innerHTML = (inner == 'false' ? USER + '-' + header : header);
	var dd = document.createElement('dd');
	dl.appendChild(dd);
	if (inner == 'false') {
		var valuesTable = document.createElement('table');
		var tr = document.createElement('tr');
		valuesTable.appendChild(tr);
		makeAttributes(tr,
					   'class', 'odd',
					   'id', makeId(subjectId, 'val', firstSubject));
		var td = document.createElement('td');
		tr.appendChild(td);
		makeAttributes(td,
					   'class', 'file-tag multivalue');
		var a = document.createElement('a');
		td.appendChild(a);
		makeAttributes(a,
					   'href', 'javascript:' + makeFunction('showColumn', index, firstSubject));
		a.innerHTML = USER + '-' + subjectGroupName + typeCode + firstSubject;
		td = document.createElement('td');
		tr.appendChild(td);
		makeAttributes(td,
					   'id', makeId(subjectId1, 'removeValue'));
		var input = document.createElement('input');
		makeAttributes(input,
					   'type', 'button',
				       'onclick', makeFunction('deleteSubject', index, firstSubject),
				       'value', 'Remove ' + value);
		td.appendChild(input);
		var newSubjectTable = document.createElement('table');
		tr = document.createElement('tr');
		newSubjectTable.appendChild(tr);
		td = document.createElement('td');
		tr.appendChild(td);
		input = document.createElement('input');
		makeAttributes(input,
					   'id', makeId(subjectId, 'subject'),
				       'tagname', value,
				       'type', 'button',
				       'onclick', makeFunction('setValue', str(subjectId), str('subject')),
				       'value', 'New ' + value);
		td.appendChild(input);
		var subjectTable = document.createElement('table');
		var tr = document.createElement('tr');
		subjectTable.appendChild(tr);
		td = document.createElement('td');
		tr.appendChild(td);
		td.appendChild(valuesTable);
		tr = document.createElement('tr');
		subjectTable.appendChild(tr);
		td = document.createElement('td');
		tr.appendChild(td);
		td.appendChild(newSubjectTable);
		dd.appendChild(subjectTable);
	}

	var subjectsId = makeId('subjects', index);
	var subject = document.createElement('table');
	var tr = document.createElement('tr');
	makeAttributes(tr,
				   'class', 'no-border');
	subject.appendChild(tr);
	td = document.createElement('td');
	tr.appendChild(td);
	var table = document.createElement('table');
	td.appendChild(table);
	makeAttributes(table,
				   'class', 'file-list');
	tr = document.createElement('tr');
	makeAttributes(tr,
				   'class', 'file-heading');
	table.appendChild(tr);
	var th = document.createElement('th');
	tr.appendChild(th);
	makeAttributes(th,
				   'class', 'file-tag');
	th.innerHTML = 'Tags';
	th = document.createElement('th');
	tr.appendChild(th);
	makeAttributes(th,
				   'id', headerId,
				   'class', 'file-tag');
	th.innerHTML = (inner == 'false' ? USER + '-' : '') + subjectGroupName + typeCode + firstSubject + suffix;
	tr = document.createElement('tr');
	table.appendChild(tr);
	makeAttributes(tr,
				   'class', 'file-footer');
	td = document.createElement('td');
	tr.appendChild(td);
	makeAttributes(td,
				   'class', 'file-tag',
				   'id', subjectsId,
				   'suffix', suffix);
	td.appendChild(addTagsElement(index));
	td = document.createElement('td');
	tr.appendChild(td);
	makeAttributes(td,
				   'class', 'file-tag',
				   'id', subjectId1);
	var input = document.createElement('input');
	makeAttributes(input,
				   'type', 'button',
				   'onclick', makeFunction('hideSubject', index, firstSubject),
				   'value', 'Hide ' + value);
	td.appendChild(input);
	dd.appendChild(subject);
	var div = document.createElement('div');
	makeAttributes(div,
				   'id', makeId(subjectId1, 'Buttons'));
	var buttons = document.createElement('input');
	makeAttributes(buttons,
					'id', makeId(subjectsId, 'Expand'),
					'type', 'button',
					'name', 'Expand',
					'onclick', makeFunction('displayExpandColumn', index),
					'style', 'display:none',
					'value', 'Show All');
	div.appendChild(buttons);
	buttons = document.createElement('input');
	makeAttributes(buttons,
					'id', makeId(subjectsId, 'Collapse'),
					'type', 'button',
					'name', 'Collapse',
					'onclick', makeFunction('displayCollapseColumn', index),
					'value', 'Hide All');
	div.appendChild(buttons);
	dd.appendChild(div);
	dd.appendChild(document.createElement('p'));
	document.getElementById('selectTag').selected = "selected";
	newTags(groupCounter.length, value);
	var id = makeId(subjectId1, value.substr(0,1).toLowerCase() + value.substr(1) + 'ID');
	var textValue = (inner == 'false' ? USER + '-' : '') + subjectGroupName + typeCode + firstSubject + suffix;
	document.getElementById(makeId(id, 'input')).value = textValue;
	makeAttributes(document.getElementById(makeId(id, 'input')),
				   'size', textValue.length);
	window.scrollTo(getLeftOffset(headerId), getTopOffset(headerId));
	return subjectGroupName + typeCode + firstSubject + suffix;
}

function handleSubjectResponse(data, textStatus, jqXHR) {
	var rows = jqXHR.responseText.split('\n');
	var values = new Array();
	for (var j=0; j<rows.length; j++) {
		if (rows[j].length > 0) {
			var index = rows[j].lastIndexOf('-') + 1;
			var val = parseInt(rows[j].substr(index));
			if (val > firstSubject) {
				firstSubject = val;
			}
		}
	}
}

function addTags(group) {
	var select_list_field = document.getElementById(makeId('addtags', group));
	var select_list_selected_index = select_list_field.selectedIndex;
	var value = select_list_field.options[select_list_selected_index].value;
	document.getElementById(makeId('addTag', group)).selected = "selected";
	newTags(group, value);
}

function setValue(id, type) {
	var value = null;
	var elemId = makeId(id, type);
	var tagname;
	var group;
	var position;
	if (type != 'button') {
		tagname = document.getElementById(elemId).getAttribute('tagname');
	} else {
		var parts = id.split('_');
		tagname = parts[parts.length - 1];
	}
	if (type == 'subject') {
		var parts = id.split('_');
		group = parts[1];
		value = newSubject(group, 'false');
		position = groupCounter[group-1];
	}
	else if (type == 'button') {
		var parent = document.getElementById(makeId(id, 'button'));
		if (parent.children.length == 0) {
			var parts = id.split('_');
			var subjectType = groupType[parts[1] - 1];
			var subjectID = makeId('Subject', parts[1], parts[2], subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID', 'input');
			var name = document.getElementById(subjectID).value;
			value = selectSubject(tagMapArray[tagname], name, '', parent, 'All ' + tagname);
			group = parent.children[0].getAttribute('id').split('_')[1];
			position = 1;
		} else {
			var parts = parent.children[0].getAttribute('id').split('_');
			group = parts[1];
			value = newSubject(group, 'true');
			position = groupCounter[group-1];
		}
	} else if (type == 'select') {
		var select_list_field = document.getElementById(elemId);
		var select_list_selected_index = select_list_field.selectedIndex;
		if (select_list_selected_index > 0) {
			value = select_list_field.options[select_list_selected_index].value;
		}
		select_list_field.selectedIndex = 0;
	} else {
		value = document.getElementById(elemId).value.replace(/^\s*/, "").replace(/\s*$/, "");
		if (value.length == 0) {
			value = null;
		}
		document.getElementById(elemId).value = '';
	}
	if (value != null) {
		if (type == 'subject') {
			addSubjectValue(value, group, position);
		}
		else if (type == 'button') {
			var parent = document.getElementById(makeId(elemId, 'entity'));
			addButtonValue(parent, value, group, position);
		}
		else {
			var suffix;
			var valId = makeId(id, 'val');
			var currentIndex = multivalueIds[valId];
			if (currentIndex == null) {
				currentIndex = 0;
			}
			multivalueIds[valId] = ++currentIndex;
			suffix = currentIndex;
			var parent = document.getElementById(id);
			addValue(parent, id, suffix, value);
		}
	}
}

function addSubjectValue(value, group, position) {
	var subjectId = makeId('Subject', group);
	var table = document.getElementById(makeId(subjectId, 'subject')).parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.children[0].children[0].children[0].children[0];
	var tr = document.createElement('tr');
	makeAttributes(tr,
				   'id', makeId(subjectId, 'val', position),
				   'class', 'odd');
	table.appendChild(tr);
	var td = document.createElement('td');
	var a = document.createElement('a');
	td.appendChild(a);
	makeAttributes(a,
				   'href', 'javascript:' + makeFunction('showColumn', group, position));
	a.innerHTML = USER + '-' + value;
	tr.appendChild(td);
	td = document.createElement('td');
	makeAttributes(td,
				   'id', makeId(subjectId, 'removeValue'));
	var input = document.createElement('input');
	makeAttributes(input,
					'type', 'button',
				    'onclick', makeFunction('deleteSubject', group, position),
				    'value', 'Remove ' + groupType[group-1]);
	td.appendChild(input);
	tr.appendChild(td);
	var headerId = makeId(subjectId, position, 'header');
	window.scrollTo(getLeftOffset(headerId), getTopOffset(headerId));
}

function addButtonValue(parent, value, group, position) {
	var subjectId = makeId('Subject', group);
	var tr = document.createElement('tr');
	makeAttributes(tr,
				   'class', 'file-tag-list',
				   'id', makeId(subjectId, 'val', position));
	var td = document.createElement('td');
	makeAttributes(td,
				   'class', 'file-tag multivalue');
	var a = document.createElement('a');
	td.appendChild(a);
	makeAttributes(a,
				   'href', 'javascript:' + makeFunction('showColumn', group, position));
	a.innerHTML = value;
	tr.appendChild(td);
	td = document.createElement('td');
	makeAttributes(td,
				   'class', 'file-tag multivalue delete',
				   'id', makeId(subjectId, 'removeValue'));
	var input = document.createElement('input');
	makeAttributes(input,
					'type', 'button',
				    'onclick', makeFunction('deleteSubject', group, position),
				    'value', 'Remove ' + groupType[group-1]);
	td.appendChild(input);
	tr.appendChild(td);
	parent.insertBefore(tr, parent.lastChild);
}

function addValue(parent, id, suffix, value) {
	var valId = suffix ? makeId(id, 'val', suffix) : makeId(id, 'val');
	var tr = document.createElement('tr');
	makeAttributes(tr,
				   'class', 'file-tag-list',
				   'id', valId);
	var td = document.createElement('td');
	makeAttributes(td,
				   'class', 'file-tag multivalue');
	td.innerHTML = value;
	tr.appendChild(td);
	td = document.createElement('td');
	makeAttributes(td,
				   'class', 'file-tag multivalue delete',
				   'id', makeId(id, 'removeValue'));
	var deleteAction = makeFunction('deleteElementById', str(valId));
	var input = document.createElement('input');
	makeAttributes(input,
				   'type', 'button',
				   'onclick', deleteAction,
				   'value', 'Remove Value');
	td.appendChild(input);
	tr.appendChild(td);
	parent.insertBefore(tr, parent.lastChild);
}

function tagCell(group, tagname, index) {
	var id = makeId('Subject', group, index, tagname);
	var inputId = makeId(id, 'input');
	var type;
	var table = document.createElement('table');
	makeAttributes(table,
					'id', makeId(id, 'setValue'),
				    'class', 'file-tag-list');
	var tr = document.createElement('tr');
	table.appendChild(tr);
	var td = document.createElement('td');
	tr.appendChild(td);
	makeAttributes(td,
				    'class', 'file-tag multivalue input');
	var options = enumArray[tagname];
	if (options == null) {
		if (linkArray[tagname] != null) {
			type = 'button';
			var tdTable = document.createElement('table');
			td.appendChild(tdTable);
			makeAttributes(tdTable,
						    'class', 'entity',
						    'id', makeId(id, 'button', 'entity'));
			var tr = document.createElement('tr');
			makeAttributes(tr,
						    'class', 'no-border');
			tdTable.appendChild(tr);
			var td = document.createElement('td');
			tr.appendChild(td);
			var input = document.createElement('input');
			makeAttributes(input,
							'type', 'button',
						    'onclick', makeFunction('setValue', str(id), str(type)),
						    'value', 'New ' + tagMapArray[tagname]);
			td.appendChild(input);
			tr = document.createElement('tr');
			tdTable.appendChild(tr);
			var td = document.createElement('td');
			tr.appendChild(td);
			makeAttributes(td,
							'id', makeId(id, 'button'),
						    'class', 'file-tag multivalue input');
		} else {
			type = 'input';
			var input = document.createElement('input');
			makeAttributes(input,
							'type', 'text',
						    'id', inputId,
						    'tagname', tagname);
			td.appendChild(input);
			if (dateArray.contains(tagname)) {
				var a = document.createElement('a');
				td.appendChild(a);
				makeAttributes(a,
								'href', 'javascript:' + makeFunction('generateCalendar', str(inputId)));
				var img = document.createElement('img');
				a.appendChild(img);
				makeAttributes(img,
								'src', resourcePrefix + 'calendar.gif',
								'width', '16',
								'height', '16',
								'border', '0',
								'alt', 'Pick a date');
			}
		}
	} else {
		type = 'select';
		var val = makeId(id, 'select');
		var select = document.createElement('select');
		td.appendChild(select);
		makeAttributes(select,
						'id', val,
						'tagname', tagname,
						'name', val);
		var option = document.createElement('option');
		select.appendChild(option);
		makeAttributes(option,
						'value', '');
		option.innerHTML = 'Select a value';
		var options = enumArray[tagname];
		for (var j=0; j<options.length; j++) {
			option = document.createElement('option');
			select.appendChild(option);
			makeAttributes(option,
							'value', options[j]);
			option.innerHTML = options[j];
		}
	}
	if (type != 'button' && multivalueArray.contains(tagname)) {
		td = document.createElement('td');
		tr.appendChild(td);
		makeAttributes(td,
						'class', 'file-tag multivalue set');
		var input = document.createElement('input');
		makeAttributes(input,
						'type', 'button',
					    'onclick', makeFunction('setValue', str(id), str(type)),
					    'value', 'Set Value');
		td.appendChild(input);
	}
	return table;
}

function addTagsElement(group) {
	var tagsId = makeId('addtags', group);
	var tagId = makeId('add', group);
	var select = document.createElement('select');
	makeAttributes(select,
					'id', tagsId,
					'name', tagsId,
					'onchange', makeFunction('addTags', group));
	var option = document.createElement('option');
	select.appendChild(option);
	makeAttributes(option,
					'id', makeId('addTag', group),
					'value', '');
	option.innerHTML = 'Add Tags';
	for (var i=0; i < groupTags.length; i++) {
		option = document.createElement('option');
		select.appendChild(option);
		makeAttributes(option,
						'id', makeId(tagId, groupTags[i]),
						'value', groupTags[i]);
		option.innerHTML = groupTags[i];
	}
	return select;
}

var HOME;
var USER;
var SVCPREFIX;
var resourcePrefix;
var allSubjects;

function init(home, user) {
	expiration_warning = false;
	HOME = home;
	USER = user;
	SVCPREFIX = home.substring(home.lastIndexOf('/') + 1);
	resourcePrefix = '/' + SVCPREFIX + '/static/';
	var select = document.getElementById("tags");
	var option = document.createElement('option');
	makeAttributes(option,
				   'id', 'selectTag',
				   'value', 'Choose Subject Type');
	option.innerHTML = 'Choose Subject Type';
	select.appendChild(option);
	for (var i=0; i < groupTags.length; i++) {
		option = document.createElement('option');
		makeAttributes(option,
					   'id', groupTags[i],
					   'value', groupTags[i]);
		option.innerHTML = groupTags[i];
		select.appendChild(option);
	}
	document.getElementById("Status").innerHTML = 'Loading the form. Please wait...';
	document.getElementById('psoc_progress_bar').style.display = '';
	totalRequests = selectArray.length;
	sentRequests = 0;
	drawProgressBar(0);
	displayStatus('sendSelectRequest()');
}

function displayStatus(request) {
	drawProgressBar(Math.ceil((sentRequests + 1) * 100 / totalRequests));
	setTimeout(request, 1);
}

function sendSelectRequest() {
	var PREFIX = HOME + '/query/';
	var SUFFIX = 'ID?versions=any';
	var url = PREFIX + selectArray[sentRequests] + SUFFIX;
	$.ajax({
		url: url,
		accepts: {text: 'text/uri-list'},
		dataType: 'text',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: handleSelectResponse,
		error: handleError
	});
}

function handleError(jqXHR, textStatus, errorThrown) {
	var err = jqXHR.getResponseHeader('X-Error-Description');
	alert(err != null ? unescape(err) : jqXHR.responseText);
	document.getElementById('psoc_progress_bar').style.display = 'none';
	document.getElementById("Status").innerHTML = '';
}

function handleSelectResponse(data, textStatus, jqXHR) {
	var rows = jqXHR.responseText.split('\n');
	var values = new Array();
	for (var j=0; j<rows.length; j++) {
		if (rows[j].length > 0) {
			var index = rows[j].lastIndexOf('=') + 1;
			values.push(decodeURIComponent(rows[j].substr(index)));
		}
	}
	enumArray[selectArray[sentRequests]] = values.sort();
	if (sharedId[selectArray[sentRequests]] != null) {
		var tags = sharedId[selectArray[sentRequests]];
		for (var j=0; j<tags.length; j++) {
		 	enumArray[tags[j]] = enumArray[selectArray[sentRequests]].slice(0);
		}
	}
	if (++sentRequests >= totalRequests) {
		document.getElementById('psoc_progress_bar').style.display = 'none';
		document.getElementById("Status").innerHTML = '';
	} else {
		displayStatus('sendSelectRequest()');
	}
}

function genericTest() {
	getAllSubjects();
	resolveDependencies();
	postSubjects();
	expiration_warning = true;
}

function getSubjectTags(group, position) {
	var result = new Array();
	var id = makeId('Subject', group, position, 'header');
	var tbody = document.getElementById(id).parentNode.parentNode;
	for (var i=1; i<tbody.children.length-1; i++) {
		var tagname = tbody.children[i].children[0].innerHTML;
		result.push(tagname);
	}
	return result;
}

function getSubjectValues(group, position, tags) {
	var result = new Array();
	for (var i=0; i<tags.length; i++) {
		var id = makeId('Subject', group, position, tags[i]);
		var tables = document.getElementById(id).children;
		if (tables.length > 1) {
			var values = new Array();
			for (var j=0; j<tables.length-1; j++) {
				var td = tables[j].children[0];
				var value;
				if (td.children.length > 0) {
					// anchor values
					value = td.children[0].innerHTML;
				} else {
					value = td.innerHTML;
				}
				values.push(value);
			}
			result[tags[i]] = values;
		} else if (tables.length == 1) {
			var td = tables[0].children[0].children[0].children[0];
			if (td.nodeName == 'SELECT') {
				var select_list_field = td;
				var select_list_selected_index = select_list_field.selectedIndex;
				if (select_list_selected_index > 0) {
					var values = new Array();
					var value = select_list_field.options[select_list_selected_index].value;
					values.push(value);
					result[tags[i]] = values;
				}
			} else if (td.nodeName == 'INPUT') {
				var value = td.value.replace(/^\s*/, "").replace(/\s*$/, "");
				if (value.length > 0) {
					var values = new Array();
					values.push(value);
					result[tags[i]] = values;
				}
			} else if (td.nodeName == 'TABLE') {
				var rows = td.children;
				if (rows.length > 2) {
					var values = new Array();
					for (var j=1; j<rows.length-1; j++) {
						var value = rows[j].children[0].children[0].innerHTML;
						values.push(value);
					}
					result[tags[i]] = values;
				}
			}
		}
	}
	return result;
}

function getAllSubjects() {
	document.getElementById('AllBody').value ='';
	allSubjects = new Array();
	var tags;
	for (var i=0; i < groupCounter.length; i++) {
		tags = null;
		for (var j=1; j<=groupCounter[i]; j++) {
			var id = makeId('Subject', i+1, j);
			if (document.getElementById(id) != null) {
				if (tags == null) {
					tags = getSubjectTags(i+1, j);
				}
				var subjectTags = new Array();
				subjectTags['values'] = getSubjectValues(i+1, j, tags);
				allSubjects[id] = subjectTags;
				if (tagsIds[tags[0]] == null) {
					tagsIds[tags[0]] = new Array();
				}
				
				var idsArray = new Array();
				idsArray[subjectTags['values'][tags[0]]] = id;
				tagsIds[tags[0]][subjectTags['values'][tags[0]]] = id;
			}
		}
	}
	for (var subject in allSubjects) {
		if (allSubjects.hasOwnProperty(subject)) {
			var values = allSubjects[subject]['values'];
			document.getElementById('AllBody').value += subject + '\n';
			for (var value in values) {
				if (values.hasOwnProperty(value)) {
					document.getElementById('AllBody').value += value + ':\n';
					var tagValues = values[value];
					for (var i=0; i<tagValues.length; i++) {
						document.getElementById('AllBody').value += '\t' + tagValues[i] + '\n';
					}
				}
			}
			document.getElementById('AllBody').value += '\n';
		}
	}
	//document.getElementById('AllBody').style.display = '';
}

var totalRequests;
var sentRequests;

function postSubjects() {
	document.getElementById('psoc_progress_bar').style.display = '';
	totalRequests = subjectsQueue.length;
	sentRequests = 0;
	document.getElementById("Status").innerHTML = 'Saving the form. Please wait...';
	document.getElementById("Error").innerHTML = '';
	displayStatus('postSubject()');
}

function postSubject() {
	// POST the subject
	var success = false;
	var url = HOME + '/subject/?incomplete&';
	var values = allSubjects[subjectsQueue[sentRequests]]['values'];
	var tags = new Array();
	for (var value in values) {
		if (values.hasOwnProperty(value)) {
			var tag = encodeURIComponent(value) + '=';
			var tagVals = new Array();
			var tagValues = values[value];
			for (var i=0; i<tagValues.length; i++) {
				tagVals.push(encodeURIComponent(tagValues[i]));
			}
			tags.push(encodeURIComponent(value) + '=' + tagVals.join(','));
		}
	}
	url += tags.join('&');
	drawProgressBar(Math.ceil((sentRequests + 1) * 100 / totalRequests));
	$.ajax({
		url: url,
		type: 'POST',
		headers: {'User-agent': 'Tagfiler/1.0', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
		data: {action: 'post'},
		async: false,
		success: handleSubmitResponse,
		error: handleSubmitError
	});
}

function handleSubmitResponse(data, textStatus, jqXHR) {
	if (++sentRequests >= totalRequests) {
		document.getElementById('psoc_progress_bar').style.display = 'none';
		document.getElementById("Status").innerHTML = '';
		subjectsQueue.length = 0;
		listSubjects();
	} else {
		displayStatus('postSubject()');
	}
}

function handleSubmitError(jqXHR, textStatus, errorThrown) {
	var p = document.createElement('p');
	document.getElementById("Error").appendChild(p);
	p.innerHTML = 'ERROR: ' + textStatus;
	var err = jqXHR.getResponseHeader('X-Error-Description');
	var br = document.createElement('br');
	document.getElementById("Error").appendChild(br);
	br = document.createElement('br');
	document.getElementById("Error").appendChild(br);
	p = document.createElement('p');
	document.getElementById("Error").appendChild(p);
	p.innerHTML = (err != null ? unescape(err) : jqXHR.responseText);
	br = document.createElement('br');
	document.getElementById("Error").appendChild(br);
	br = document.createElement('br');
	document.getElementById("Error").appendChild(br);
	document.getElementById('psoc_progress_bar').style.display = 'none';
	document.getElementById("Status").innerHTML = '';
}

function resolveDependencies() {
	for (var subject in allSubjects) {
		if (allSubjects.hasOwnProperty(subject)) {
			if (!subjectsQueue.contains(subject)) {
				addToQueue(subject);
			}
		}
	}
}

function addToQueue(subject) {
	var values = allSubjects[subject]['values'];
	var first = true;
	for (var value in values) {
		if (values.hasOwnProperty(value)) {
			if (first) {
				first = false;
				continue;
			}
			if (tagsMap[value] != null) {
				var mapValue = tagsMap[value];
				var tagValues = values[value];
				for (var i=0; i<tagValues.length; i++) {
					if (tagsIds[mapValue] != null && tagsIds[mapValue][tagValues[i]] != null) {
						addToQueue(tagsIds[mapValue][tagValues[i]]);
					}
				}
			}
		}
	}
	if (!subjectsQueue.contains(subject)) {
		subjectsQueue.push(subject);
	}
}

function listSubjects() {
	var ul = document.createElement('ul');
	var psoc = document.getElementById('psoc');
	for (var subject in allSubjects) {
		if (allSubjects.hasOwnProperty(subject)) {
			var li = document.createElement('li');
			li.innerHTML = document.getElementById(subject + '_header').innerHTML;
			ul.appendChild(li);
		}
	}
	psoc.innerHTML = '';
	var h2 = document.createElement('h2');
	psoc.appendChild(h2);
	h2.innerHTML = 'Completed';
	var p = document.createElement('p');
	psoc.appendChild(p);
	var b = document.createElement('b');
	p.appendChild(b);
	makeAttributes(b,
				   'style', 'color:green');
	b.innerHTML = 'All subjects were successfully created.';
	p = document.createElement('p');
	psoc.appendChild(p);
	p.innerHTML = 'See below for a summary of the subjects.';
	psoc.appendChild(ul);
}

var subjectsQueue = new Array();
var tagsIds = new Array();

var tagsMap = {
	'experiment' : 'experimentID',
	'lab' : 'labID',
	'mice' : 'mouseID',
	'mouse' : 'mouseID',
	'observation' : 'observationID',
	'observations' : 'observationID',
	'performer' : 'researcherID',
	'principal' : 'researcherID',
	'sample' : 'sampleID',
	'samples' : 'sampleID',
	'site' : 'siteID',
	'supplier' : 'supplierID',
	'treatment' : 'treatmentID'
}