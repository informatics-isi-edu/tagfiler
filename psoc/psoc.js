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

var tagMap = {
	'start age' : 'startAge',
	'mouse strain' : 'mouseStrain',
	'lot#' : 'lot',
	'cancer type' : 'cancerType',
	'#cells' : 'cells',
	'sample type' : 'sampleType',
	'serum sample type' : 'serumSampleType'
}

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

function getId(tag) {
	var tagId = tagMap[tag];
	return (tagId != null ? tagId : tag);
}

function getChild(item, index) {
	return item.children(':nth-child(' + index + ')');
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

function getLeftOffset(id) {
	var elem = $('#' + id);
	var offset = elem.offset().left;
	return offset;
}

function getTopOffset(id) {
	var elem = $('#' + id);
	var offset = elem.offset().top;
	return offset;
}

function deleteElementById(id) {
	var elem = $('#' + id);
	elem.remove();
}

function deleteColumn(id) {
	var row = $('#' + id).parent();
	var table = row.parent();
	var index = 0;
	var count = row.children().size();
	for (var i=1; i <= count; i++) {
		if (getChild(row, i).attr('id') == id) {
			index = i;
			break;
		}
	}
	count = table.children().size();
	for (var i=1; i <= count; i++) {
		var row = getChild(table, i);
		getChild(row, index).remove();
	}
}

function getColumnIndex(id) {
	var row = $('#' + id).parent();
	var count = row.children().size();
	var index = -1;
	for (var i=1; i <= count; i++) {
		if (getChild(row, i).attr('id') == id) {
			index = i;
			break;
		}
	}
	return index;
}

function getVisibleColumn(group) {
	var id = makeId('subjects', group);
	var row = $('#' + id).parent();
	var position = -1;
	var count = row.children().size();
	for (var i=2; i <= count; i++) {
		if (!getChild(row, i).is(':hidden')) {
			position = i;
			break;
		}
	}
	return position;
}

function getHideColumn(group) {
	var id = makeId('subjects', group);
	var row = $('#' + id).parent();
	var position = -1;
	var count = row.children().size();
	for (var i=2; i <= count; i++) {
		if (getChild(row, i).is(':hidden')) {
			position = i;
			break;
		}
	}
	return position;
}

function getVisibleColumnCount(group) {
	var id = makeId('subjects', group);
	var row = $('#' + id).parent();
	var total = 0;
	var count = row.children().size();
	for (var i=2; i <= count; i++) {
		if (!getChild(row, i).is(':hidden')) {
			total++;
		}
	}
	return total;
}

function hideColumn(group, position) {
	var id = makeId('subjects', group);
	var table = $('#' + id).parent().parent();
	var count = table.children().size();
	for (var i=1; i <= count; i++) {
		var row = getChild(table, i);
		getChild(row, position).css('display', 'none');
	}
}

function displayColumn(group, position) {
	var id = makeId('subjects', group);
	var table = $('#' + id).parent().parent();
	var count = table.children().size();
	for (var i=1; i <= count; i++) {
		var row = getChild(table, i);
		getChild(row, position).css('display', '');
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
	var dt = $('#' + makeId('Subject', group, 'span'));
	if (dt.next().css('display') == 'none') {
		var span = getChild(dt, 1);
		var table = getChild(span, 1);
		table = getChild(table, 1);
		var tbody = getChild(table, 1);
		var row = getChild(tbody, 1);
		var td = getChild(row, 2);
		var header = td.html();
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
	$('#' + expandId).css('display', 'none');
	$('#' + collapseId).css('display', 'none');

	var count = getVisibleColumnCount(group);
	var subjects = $('#' + id).parent().children().size()-1;
	if (count > 0) {
		$('#' + collapseId).css('display', '');
	}
	if (count < subjects) {
		$('#' + expandId).css('display', '');
	}
}

function appendColumn(id, values) {
	var row = $('#' + id).parent();
	var table = row.parent();
	var count = table.children().size();
	for (var i=0; i <= count; i++) {
		getChild(table, i+1).append(values[i]);
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
	var table = $('#' + makeId('subjects', group)).parent().parent();
	var rowClass = 'even';
	for (var i=0; i<newTags.length; i++) {
		var row = $('<tr>');
		makeAttributes(row,
					   'class', 'file-tag ' + rowClass);
		rowClass = (rowClass == 'odd') ? 'even' : 'odd';
		var td = $('<td>');
		makeAttributes(td,
					   'class', 'file-tag');
		td.html(newTags[i]);
		row.append(td);
		for (var j=1; j <= groupCounter[group-1]; j++) {
			var subjectId = makeId('Subject', group, j);
			if ($('#' + subjectId).length == 0) {
				// subject might have been deleted
				continue;
			}
			var id = makeId(subjectId, getId(newTags[i]));
			var td = $('<td>');
			makeAttributes(td,
						   'nowrap', 'nowrap',
						   'id', id,
						   'class', 'file-tag');
			td.append(tagCell(group, newTags[i], j));
			row.append(td);
		}
		row.insertBefore(table.children(':last-child'));
	}
	makeAttributes(table.children(':last-child'),
				   'class', 'file-footer ' + rowClass);
}

function newSubject(group, inner) {
	var typeCode = groupType[group-1] + '-';
	if (inner == 'true') {
		typeCode = '-' + groupType[group-1] + '-';
	}
	var subjectsId = makeId('subjects', group);
	var suffix = $('#' + subjectsId).attr('suffix');
	var values = new Array();
	var countIndex = groupCounter[group-1] + 1;
	var subjectId = makeId('Subject', group, countIndex);
	groupCounter[group-1] = countIndex;
	var th = $('<th>');
	makeAttributes(th,
				   'class', 'file-tag',
				   'id', makeId(subjectId, 'header'));
	th.html((inner == 'false' ? USER + '-' : '') + groupName[group-1] + typeCode + countIndex + suffix);
	values.push(th);
	for (var i=0; i<selectedTags[group-1].length; i++) {
		var id = makeId(subjectId, getId(selectedTags[group-1][i]));
		var td = $('<td>');
		makeAttributes(td,
					   'nowrap', 'nowrap',
					   'id', id,
					   'class', 'file-tag entity');
		td.append(tagCell(group, selectedTags[group-1][i], countIndex));
		values.push(td);
	}
	var td = $('<td>');
	makeAttributes(td,
				   'id', subjectId,
				   'class', 'file-tag');
	var input = $('<input>');
	makeAttributes(input,
				   'type', 'button',
				   'onclick', makeFunction('hideSubject', group, countIndex),
				   'value', 'Hide ' + groupType[group-1]);
	td.append(input);
	values.push(td);
	appendColumn(subjectsId, values);
	var id = makeId(subjectId, groupType[group-1].substr(0,1).toLowerCase() + groupType[group-1].substr(1) + 'ID');
	var subjectName = groupName[group-1] + typeCode + countIndex + suffix;
	var textValue = (inner == 'false' ? USER + '-' + subjectName : subjectName);
	$('#' + makeId(id, 'input')).val(textValue);
	makeAttributes($('#' + makeId(id, 'input')),
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
	var row = $('#' + id).parent();
	deleteColumn(id);
	if (row.children().size() == 1) {
		// the div that contains the table;
		id = makeId('Subject', group, 1, 'container');
		var div = $('#' + id);
		div.remove();
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
	var value = $('#tags option:selected').text();
	var subjectGroupName;
	while (true) {
		subjectGroupName = prompt(value + ' name:');
		if (subjectGroupName == null) {
			// cancel
			$('#selectTag').selected = 'selected';
			return;
		}
		subjectGroupName = subjectGroupName.replace(/^\s*/, '').replace(/\s*$/, '');
		if (subjectGroupName.length > 0) {
			break;
		} else {
			alert(value + ' name can not be empty.');
		}
	}
	selectSubject(value, subjectGroupName + '-', null, $('#all_subjects'), subjectGroupName);
	$('#selectTag').attr('selected', 'selected');
	$('#NewSubject').attr('disabled', 'disabled');
	$('#GetSubject').attr('disabled', 'disabled');
}

function enableSubjectButtons() {
	if ($('#tags').children('option:selected').index() > 0) {
		$('#NewSubject').removeAttr('disabled');
		$('#GetSubject').removeAttr('disabled');
	}
}

function tog(dt, header) {
	var dd = dt.next();
	var toOpen = (dd.css('display') == 'none');
	dd.css('display', toOpen ? '' : 'none');
	var spans = dt.children('span');
	var span = getChild(spans, 1);
	span.html('');
	var spanTitle = $('<table>');
	span.append(spanTitle);
	var tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'no-border');
	spanTitle.append(tr);
	var td = $('<td>');
	tr.append(td);
	var img = $('<img>');
	makeAttributes(img,
				   'src', resourcePrefix + (toOpen ? 'minus.png' : 'plus.png'),
				   'width', '16',
				   'height', '16',
				   'border', '0',
				   'alt', (toOpen ? '-' : '+'));
	td.append(img);
	td = $('<td>');
	tr.append(td);
	td.html(header);
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
	suffix = suffix.replace(/^\s*/, '').replace(/\s*$/, '');
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
		$('#all_subjects').css('display', 'block');
	}
	var index = groupCounter.length;

	var subjectId = makeId('Subject', index);
	var subjectId1 = makeId(subjectId, firstSubject);
	var headerId = makeId(subjectId1, 'header');
	var container = $('<div>');
	makeAttributes(container,
				   'id', makeId(subjectId1, 'container'));
	parent.append(container);
	var dl = $('<dl>');
	container.append(dl);
	var dt = $('<dt>');
	makeAttributes(dt,
				   'onclick', makeFunction('tog', '$(this)', str((inner == 'false' ? USER + '-' + header : header))),
				   'id', makeId(subjectId, 'span'));
	dl.append(dt);
	var span = $('<span>');
	makeAttributes(span,
				   'style', 'color: blue; cursor: default');
	dt.append(span);
	var spanTitle = $('<table>');
	span.append(spanTitle);
	var tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'no-border');
	spanTitle.append(tr);
	var td = $('<td>');
	tr.append(td);
	var img = $('<img>');
	makeAttributes(img,
				   'src', resourcePrefix + 'minus.png',
				   'width', '16',
				   'height', '16',
				   'border', '0',
				   'alt', '-');
	td.append(img);
	td = $('<td>');
	tr.append(td);
	td.html(inner == 'false' ? USER + '-' + header : header);
	var dd = $('<dd>');
	dl.append(dd);
	if (inner == 'false') {
		var valuesTable = $('<table>');
		var tr = $('<tr>');
		makeAttributes(tr,
					   'class', 'odd',
					   'id', makeId(subjectId, 'val', firstSubject));
		valuesTable.append(tr);
		var td = $('<td>');
		makeAttributes(td,
					   'class', 'file-tag multivalue');
		tr.append(td);
		var a = $('<a>');
		makeAttributes(a,
					   'href', 'javascript:' + makeFunction('showColumn', index, firstSubject));
		a.html(USER + '-' + subjectGroupName + typeCode + firstSubject);
		td.append(a);
		td = $('<td>');
		makeAttributes(td,
					   'id', makeId(subjectId1, 'removeValue'));
		tr.append(td);
		var input = $('<input>');
		makeAttributes(input,
					   'type', 'button',
				       'onclick', makeFunction('deleteSubject', index, firstSubject),
				       'value', 'Remove ' + value);
		td.append(input);
		var newSubjectTable = $('<table>');
		tr = $('<tr>');
		newSubjectTable.append(tr);
		td = $('<td>');
		tr.append(td);
		input = $('<input>');
		makeAttributes(input,
					   'id', makeId(subjectId, 'subject'),
				       'tagname', value,
				       'type', 'button',
				       'onclick', makeFunction('setValue', str(subjectId), str('subject')),
				       'value', 'New ' + value);
		td.append(input);
		var subjectTable = $('<table>');
		var tr = $('<tr>');
		subjectTable.append(tr);
		td = $('<td>');
		tr.append(td);
		td.append(valuesTable);
		tr = $('<tr>');
		subjectTable.append(tr);
		td = $('<td>');
		tr.append(td);
		td.append(newSubjectTable);
		dd.append(subjectTable);
	}

	var subjectsId = makeId('subjects', index);
	var subject = $('<table>');
	var tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'no-border');
	subject.append(tr);
	td = $('<td>');
	tr.append(td);
	var table = $('<table>');
	makeAttributes(table,
				   'class', 'file-list');
	td.append(table);
	tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'file-heading');
	table.append(tr);
	var th = $('<th>');
	makeAttributes(th,
				   'class', 'file-tag');
	tr.append(th);
	th.html('Tags');
	th = $('<th>');
	makeAttributes(th,
				   'id', headerId,
				   'class', 'file-tag');
	th.html((inner == 'false' ? USER + '-' : '') + subjectGroupName + typeCode + firstSubject + suffix);
	tr.append(th);
	tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'file-footer');
	table.append(tr);
	td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag',
				   'id', subjectsId,
				   'suffix', suffix);
	tr.append(td);
	td.append(addTagsElement(index));
	td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag',
				   'id', subjectId1);
	tr.append(td);
	var input = $('<input>');
	makeAttributes(input,
				   'type', 'button',
				   'onclick', makeFunction('hideSubject', index, firstSubject),
				   'value', 'Hide ' + value);
	td.append(input);
	dd.append(subject);
	var div = $('<div>');
	makeAttributes(div,
				   'id', makeId(subjectId1, 'Buttons'));
	var buttons = $('<input>');
	makeAttributes(buttons,
					'id', makeId(subjectsId, 'Expand'),
					'type', 'button',
					'name', 'Expand',
					'onclick', makeFunction('displayExpandColumn', index),
					'style', 'display:none',
					'value', 'Show All');
	div.append(buttons);
	buttons = $('<input>');
	makeAttributes(buttons,
					'id', makeId(subjectsId, 'Collapse'),
					'type', 'button',
					'name', 'Collapse',
					'onclick', makeFunction('displayCollapseColumn', index),
					'value', 'Hide All');
	div.append(buttons);
	dd.append(div);
	dd.append($('<p>'));
	$('#selectTag').attr('selected', 'selected');
	newTags(groupCounter.length, value);
	var id = makeId(subjectId1, value.substr(0,1).toLowerCase() + value.substr(1) + 'ID');
	var textValue = (inner == 'false' ? USER + '-' : '') + subjectGroupName + typeCode + firstSubject + suffix;
	$('#' + makeId(id, 'input')).val(textValue);
	makeAttributes($('#' + makeId(id, 'input')),
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
	var value = $('#' + makeId('addtags', group) + ' option:selected').text();
	$('#' + makeId('addTag', group)).attr('selected', 'selected');
	newTags(group, value);
}

function setValue(id, type) {
	var value = null;
	var elemId = makeId(id, type);
	var tagname;
	var group;
	var position;
	if (type != 'button') {
		tagname = $('#' + elemId).attr('tagname');
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
		var parent = $('#' + makeId(id, 'button'));
		if (parent.children().size() == 0) {
			var parts = id.split('_');
			var subjectType = groupType[parts[1] - 1];
			var subjectID = makeId('Subject', parts[1], parts[2], subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID', 'input');
			var name = $('#' + subjectID).val();
			value = selectSubject(tagMapArray[tagname], name, '', parent, 'All ' + tagname);
			group = getChild(parent, 1).attr('id').split('_')[1];
			position = 1;
		} else {
			var parts = getChild(parent, 1).attr('id').split('_');
			group = parts[1];
			value = newSubject(group, 'true');
			position = groupCounter[group-1];
		}
	} else if (type == 'select') {
		if ($('#' + elemId).val() > 1) {
			value = $('#' + elemId +' option:selected').text();
		}
	} else {
		value = $('#' + elemId).val().replace(/^\s*/, '').replace(/\s*$/, '');
		if (value.length == 0) {
			value = null;
		}
		$('#' + elemId).val('');
	}
	if (value != null) {
		if (type == 'subject') {
			addSubjectValue(value, group, position);
		}
		else if (type == 'button') {
			var parent = $('#' + makeId(elemId, 'entity'));
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
			var parent = $('#' + id);
			addValue(parent, id, suffix, value);
		}
	}
}

function addSubjectValue(value, group, position) {
	var subjectId = makeId('Subject', group);
	var parent = $('#' + makeId(subjectId, 'subject')).parent();
	
	while(!parent.is('TABLE')) {
		parent = parent.parent();
	}
	while(!parent.is('TBODY')) {
		parent = parent.parent();
	}
	
	var table = getChild(parent, 1);
	while(!table.is('TBODY')) {
		table = getChild(table, 1);
	}

	var tr = $('<tr>');
	makeAttributes(tr,
				   'id', makeId(subjectId, 'val', position),
				   'class', 'odd');
	table.append(tr);
	var td = $('<td>');
	var a = $('<a>');
	makeAttributes(a,
				   'href', 'javascript:' + makeFunction('showColumn', group, position));
	a.html(USER + '-' + value);
	td.append(a);
	tr.append(td);
	td = $('<td>');
	makeAttributes(td,
				   'id', makeId(subjectId, 'removeValue'));
	var input = $('<input>');
	makeAttributes(input,
					'type', 'button',
				    'onclick', makeFunction('deleteSubject', group, position),
				    'value', 'Remove ' + groupType[group-1]);
	td.append(input);
	tr.append(td);
	var headerId = makeId(subjectId, position, 'header');
	window.scrollTo(getLeftOffset(headerId), getTopOffset(headerId));
}

function addButtonValue(parent, value, group, position) {
	var subjectId = makeId('Subject', group);
	var tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'file-tag-list',
				   'id', makeId(subjectId, 'val', position));
	var td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag multivalue');
	var a = $('<a>');
	makeAttributes(a,
				   'href', 'javascript:' + makeFunction('showColumn', group, position));
	a.html(value);
	td.append(a);
	tr.append(td);
	td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag multivalue delete',
				   'id', makeId(subjectId, 'removeValue'));
	var input = $('<input>');
	makeAttributes(input,
					'type', 'button',
				    'onclick', makeFunction('deleteSubject', group, position),
				    'value', 'Remove ' + groupType[group-1]);
	td.append(input);
	tr.append(td);
	tr.insertBefore(parent.children(':last-child'));
}

function addValue(parent, id, suffix, value) {
	var valId = suffix ? makeId(id, 'val', suffix) : makeId(id, 'val');
	var tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'file-tag-list',
				   'id', valId);
	var td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag multivalue');
	td.html(value);
	tr.append(td);
	td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag multivalue delete',
				   'id', makeId(id, 'removeValue'));
	var deleteAction = makeFunction('deleteElementById', str(valId));
	var input = $('<input>');
	makeAttributes(input,
				   'type', 'button',
				   'onclick', deleteAction,
				   'value', 'Remove Value');
	td.append(input);
	tr.append(td);
	tr.insertBefore(parent.children(':last-child'));
}

function tagCell(group, tagname, index) {
	var id = makeId('Subject', group, index, getId(tagname));
	var inputId = makeId(id, 'input');
	var type;
	var table = $('<table>');
	makeAttributes(table,
					'id', makeId(id, 'setValue'),
				    'class', 'file-tag-list');
	var tr = $('<tr>');
	table.append(tr);
	var td = $('<td>');
	makeAttributes(td,
				    'class', 'file-tag multivalue input');
	tr.append(td);
	var options = enumArray[tagname];
	if (options == null) {
		if (linkArray[tagname] != null) {
			type = 'button';
			var tdTable = $('<table>');
			makeAttributes(tdTable,
						    'class', 'entity',
						    'id', makeId(id, 'button', 'entity'));
			td.append(tdTable);
			var tr = $('<tr>');
			makeAttributes(tr,
						    'class', 'no-border');
			tdTable.append(tr);
			var td = $('<td>');
			tr.append(td);
			var input = $('<input>');
			makeAttributes(input,
							'type', 'button',
						    'onclick', makeFunction('setValue', str(id), str(type)),
						    'value', 'New ' + tagMapArray[tagname]);
			td.append(input);
			tr = $('<tr>');
			tdTable.append(tr);
			var td = $('<td>');
			tr.append(td);
			makeAttributes(td,
							'id', makeId(id, 'button'),
						    'class', 'file-tag multivalue input');
		} else {
			type = 'input';
			var input = $('<input>');
			makeAttributes(input,
							'type', 'text',
						    'id', inputId,
						    'tagname', tagname);
			td.append(input);
			if (dateArray.contains(tagname)) {
				var a = $('<a>');
				td.append(a);
				makeAttributes(a,
								'href', 'javascript:' + makeFunction('generateCalendar', str(inputId)));
				var img = $('<img>');
				makeAttributes(img,
								'src', resourcePrefix + 'calendar.gif',
								'width', '16',
								'height', '16',
								'border', '0',
								'alt', 'Pick a date');
				a.append(img);
			}
		}
	} else {
		type = 'select';
		var val = makeId(id, 'select');
		var select = $('<select>');
		makeAttributes(select,
						'id', val,
						'tagname', tagname,
						'name', val);
		td.append(select);
		var option = $('<option>');
		makeAttributes(option,
						'value', '');
		option.html('Select a value');
		select.append(option);
		var options = enumArray[tagname];
		for (var j=0; j<options.length; j++) {
			option = $('<option>');
			makeAttributes(option,
							'value', options[j]);
			option.text(options[j]);
			select.append(option);
		}
	}
	if (type != 'button' && multivalueArray.contains(tagname)) {
		td = $('<td>');
		makeAttributes(td,
						'class', 'file-tag multivalue set');
		tr.append(td);
		var input = $('<input>');
		makeAttributes(input,
						'type', 'button',
					    'onclick', makeFunction('setValue', str(id), str(type)),
					    'value', 'Set Value');
		td.append(input);
	}
	return table;
}

function addTagsElement(group) {
	var tagsId = makeId('addtags', group);
	var tagId = makeId('add', group);
	var select = $('<select>');
	makeAttributes(select,
					'id', tagsId,
					'name', tagsId,
					'onchange', makeFunction('addTags', group));
	var option = $('<option>');
	makeAttributes(option,
					'id', makeId('addTag', group),
					'value', '');
	option.text('Add Tags');
	select.append(option);
	for (var i=0; i < groupTags.length; i++) {
		option = $('<option>');
		makeAttributes(option,
						'id', makeId(tagId, groupTags[i]),
						'value', groupTags[i]);
		option.text(groupTags[i]);
		select.append(option);
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
	var select = $('#tags');
	var option = $('<option>');
	makeAttributes(option,
				   'id', 'selectTag',
				   'value', 'Choose Subject Type');
	option.text('Choose Subject Type');
	select.append(option);
	for (var i=0; i < groupTags.length; i++) {
		option = $('<option>');
		makeAttributes(option,
					   'id', getId(groupTags[i]),
					   'value', groupTags[i]);
		option.text(groupTags[i]);
		select.append(option);
	}
	$('#psoc_progress_bar').css('display', '');
	$('#Status').html('Loading the form. Please wait...');
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
	$('#psoc_progress_bar').css('display', 'none');
	$('#Status').html('');
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
		$('#psoc_progress_bar').css('display', 'none');
		$('#Status').html('');
	} else {
		displayStatus('sendSelectRequest()');
	}
}

function getSubject() {
	var PREFIX = HOME + '/tags/';
	var subjectType = $('#tags option:selected').text();
	var subjectGroupName = prompt('Enter ' + subjectType + ' name:');;
	if (subjectGroupName != null) {
		subjectGroupName = subjectGroupName.replace(/^\s*/, '').replace(/\s*$/, '');
	}
	if (subjectGroupName == null || subjectGroupName.length == 0) {
		return;
	}
	var position = prompt('Enter ' + subjectType + ' #:');;
	if (position != null) {
		position = position.replace(/^\s*/, '').replace(/\s*$/, '');
	}
	if (position == null || position.length == 0) {
		return;
	}
	var SUFFIX = subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID=' + USER + '-' + subjectGroupName + '-' + subjectType + '-' + position;
	var url = PREFIX + SUFFIX;
	getSubjectEntity(subjectType, subjectGroupName + '-', url, null, $('#all_subjects'), subjectGroupName, 0, 0);
	$('#selectTag').attr('selected', 'selected');
	$('#NewSubject').attr('disabled', 'disabled');
	$('#GetSubject').attr('disabled', 'disabled');
}

function getSubjectEntity(subjectType, subjectGroupName, url, suffix, parent, header, index, parentGroup) {
	var idTag = subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID';
	var objId;
	var group;
	
	if (index == 0) {
		// new group
		selectSubject(subjectType, subjectGroupName, suffix, parent, header);
		group = groupCounter.length;
	} else {
		// extend existing group
		var parts = getChild(parent, 1).attr('id').split('_');
		newSubject(parts[1], 'true');
		group = parentGroup;
	}
	
	var position = groupCounter[group-1];

	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
					$.each(data, function(i, object) {
						objId = object[idTag];
						$.each(object, function(key, val) {
							if ($.type(val) != 'null' && ($.type(val) != 'string' || val != 'None')) {
								if (key == idTag) {
									var id = makeId('Subject', group, position, 'header');
									$('#' + id).html(val);
									id = makeId('Subject', group, 'val', position);
									var tr = $('#' + id);
									var td = getChild(tr, 1);
									var a = getChild(td, 1);
									a.html(val);
								}
								var id = makeId('Subject', group, position, getId(key));
								var tables = $('#' + id).children();
								var table = getChild(tables, 1);
								var tbody = getChild(table, 1);
								var row = getChild(tbody, 1);
								var td = getChild(row, 1);
								if ($.type(val) == 'array') {
									// multivalue tag
									var tag = tagMapArray[key];
									if (tag != null) {
										// inner subjects
										var arrayParent = $('#' + makeId(id, 'button'));
										var urlRoot = HOME + '/tags/' + tag.substr(0,1).toLowerCase() + tag.substr(1) + 'ID=';
										var arrayGroup = group;
										$.each(val, function(j, value) {
											getSubjectEntity(tag, objId, urlRoot + encodeURIComponent(value), '', arrayParent, 'All ' + key, j, arrayGroup);
											var arrayPosition;
											if (j == 0) {
												arrayGroup = getChild(arrayParent, 1).attr('id').split('_')[1];
												arrayPosition = 1;
											} else {
												var parts = getChild(arrayParent, 1).attr('id').split('_');
												arrayGroup = parts[1];
												arrayPosition = groupCounter[arrayGroup-1];
											}
											addButtonValue(arrayParent, value, arrayGroup, arrayPosition);
										});
									} else {
										// multivalue
										var valId = makeId(id, 'val');
										var arrayParent = $('#' + id);
										$.each(val, function(j, value) {
											var currentIndex = multivalueIds[valId];
											if (currentIndex == null) {
												currentIndex = 0;
											}
											multivalueIds[valId] = ++currentIndex;
											addValue(arrayParent, id, currentIndex, value);
										});
									}
								} else {
									if (td.is('SELECT')) {
										td.val(val);
									} else if (td.is('INPUT')) {
										id = makeId(id, 'input');
										$('#' + id).val(val);
									} else if (td.is('TABLE')) {
									} else {
									}
								}
							}
						});
					});
				},
		error: handleError
	});
}

function submitForm() {
	getAllSubjects();
	resolveDependencies();
	postSubjects();
	expiration_warning = true;
}

function getSubjectTags(group, position) {
	var result = new Array();
	var id = makeId('Subject', group, position, 'header');
	var tbody = $('#' + id).parent().parent();
	for (var i=2; i<=tbody.children().size()-1; i++) {
		var row = getChild(tbody, i);
		var tagname = getChild(row, 1).html();
		result.push(tagname);
	}
	return result;
}

function getSubjectValues(group, position, tags) {
	var result = new Array();
	for (var i=0; i<tags.length; i++) {
		var id = makeId('Subject', group, position, getId(tags[i]));
		var tables = $('#' + id).children();
		if (tables.size() > 1) {
			var item = $('#' + id);
			var values = new Array();
			for (var j=1; j<=tables.size()-1; j++) {
				var row = getChild(item, j);
				var td = getChild(row, 1);
				values.push(td.html());
			}
			result[tags[i]] = values;
		} else if (tables.size() == 1) {
			var table = getChild(tables, 1);
			var tbody = getChild(table, 1);
			var row = getChild(tbody, 1);
			var td = getChild(row, 1);
			if (td.is('SELECT')) {
				if (td.children('option:selected').index() > 0) {
					var values = new Array();
					var value = td.val();
					values.push(value);
					result[tags[i]] = values;
				}
			} else if (td.is('INPUT')) {
				var value = td.val().replace(/^\s*/, '').replace(/\s*$/, '');
				if (value.length > 0) {
					if (dateArray.contains(tags[i]) && !validateDate(value)) {
						alert('Invalid value for date tag "' + tags[i] + '". Expected format is "yyyy-mm-dd".');
						return;
					}
					var values = new Array();
					values.push(value);
					result[tags[i]] = values;
				}
			} else if (td.is('TABLE')) {
				var rows = td.children();
				if (rows.size() > 1) {
					var values = new Array();
					for (var j=1; j<=rows.size()-1; j++) {
						var table = getChild(td, j);
						var row = getChild(table, 1);
						var value = getChild(row, 1).html();
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
	allSubjects = new Array();
	var tags;
	for (var i=0; i < groupCounter.length; i++) {
		tags = null;
		for (var j=1; j<=groupCounter[i]; j++) {
			var id = makeId('Subject', i+1, j);
			if ($('#' + id).length != 0) {
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
			var bodyVal = $('#AllBody').val();
			bodyVal += subject + '\n';
			for (var value in values) {
				if (values.hasOwnProperty(value)) {
					bodyVal += value + ':\n';
					var tagValues = values[value];
					for (var i=0; i<tagValues.length; i++) {
						bodyVal += '\t' + tagValues[i] + '\n';
					}
				}
			}
			bodyVal += '\n';
			$('#AllBody').val(bodyVal);
		}
	}
	//$('#AllBody').css('display', '');
}

var totalRequests;
var sentRequests;

function postSubjects() {
	$('#psoc_progress_bar').css('display', '');
	totalRequests = subjectsQueue.length;
	sentRequests = 0;
	$('#Status').html('Saving the form. Please wait...');
	$('#Error').html('');
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
		$('#psoc_progress_bar').css('display', 'none');
		$('#Status').html('');
		subjectsQueue.length = 0;
		listSubjects();
	} else {
		displayStatus('postSubject()');
	}
}

function handleSubmitError(jqXHR, textStatus, errorThrown) {
	var p = $('<p>');
	$('#Error').append(p);
	p.html('ERROR: ' + errorThrown);
	var err = jqXHR.getResponseHeader('X-Error-Description');
	p = $('<p>');
	$('#Error').append(p);
	p.html(err != null ? unescape(err) : jqXHR.responseText);
	$('#psoc_progress_bar').css('display', 'none');
	$('#Status').html('');
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
	var ul = $('<ul>');
	var psoc = $('#psoc');
	for (var subject in allSubjects) {
		if (allSubjects.hasOwnProperty(subject)) {
			var li = $('<li>');
			li.html($('#' + subject + '_header').html());
			ul.append(li);
		}
	}
	psoc.html('');
	var h2 = $('<h2>');
	psoc.append(h2);
	h2.html('Completed');
	var p = $('<p>');
	psoc.append(p);
	var b = $('<b>');
	makeAttributes(b,
				   'style', 'color:green');
	p.append(b);
	b.html('All subjects were successfully created.');
	p = $('<p>');
	psoc.append(p);
	p.html('See below for a summary of the subjects.');
	psoc.append(ul);
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

function validateDate(value) {
	var OK = false;
	try {
		var values = value.split('-');
		if (values.length == 3) {
			var year = parseInt(values[0]);
			var month = parseInt(values[1]);
			var day = parseInt(values[2]);
			var leapYear = (((year % 4) == 0) && ((year % 100) != 0) || ((year % 400) == 0));
			if (day <= DaysInMonth[month-1] || (month == 2 && leapYear && day == 29)) {
				OK = true;
			}
		}
	}
	catch (e) {
	}
	return OK;
}