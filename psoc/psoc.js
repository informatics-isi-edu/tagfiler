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

var tagsArray;
var allTags;

var tagMap = {
	'start age' : 'startAge',
	'mouse strain' : 'mouseStrain',
	'lot#' : 'lot',
	'cancer type' : 'cancerType',
	'cell type' : 'cellType',
	'#cells' : 'cells',
	'sample type' : 'sampleType',
	'serum sample type' : 'serumSampleType'
}

var selectArray = 'lab	researcher	site	supplier	treatment'.split('\t');
var sharedId = new Array();
sharedId['researcher'] = 'performer	principal'.split('\t');

var enumArray;
var linkArray;
var tagMapArray;
var dateArray;
var multivalueArray;
var groupTags;

var subjectArray = new Array();

var groupCounter = new Array();
var groupContainer = new Array();
var groupName = new Array();
var groupType = new Array();

var selectedTags = new Array();
var multivalueIds = new Array();

var newGroup = new Object();
var subjectMax = new Object();
var subjectTemplates = new Object();

var firstSubject;
var firstMouseId;

function str(value) {
	return '\'' + value + '\'';
}

function getTagTitle(tag) {
	var title = (tag == 'Mouse' ? 'Mice' : tag + 's');
	return title;
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

function showColumn(group, index, headerId) {
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
	var parts = headerId.split('_');
	var group = parts[1];
	var spanId = makeId('Subject', group, 'span');
	window.scrollTo(getLeftOffset(spanId), getTopOffset(spanId));
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
	var tags;	
	var tagsValues;
	var position = groupCounter[group-1];
	var id = makeId('Subject', group, position, 'header');
	var tagId = groupType[group-1].substr(0,1).toLowerCase() + groupType[group-1].substr(1) + 'ID';
	while ($('#' + id).length == 0 && position >= 1) {
		position--;
	}
	if (position >= 1) {
		tags = getSubjectTags(group, position);	
		tagsValues = getSubjectValues(group, position, tags);
	}
	
	var typeCode = '#';
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
	th.html(groupType[group-1] + ' ' + groupName[group-1] + typeCode + countIndex + suffix);
	values.push(th);
	for (var i=0; i<selectedTags[group-1].length; i++) {
		id = makeId(subjectId, getId(selectedTags[group-1][i]));
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
	
	// copy the values from the previous
	if (tags != null) {
		id = makeId('Subject', group, groupCounter[group-1]);
		$.each(tagsValues, function(tag, values) {
			if (!multivalueArray.contains(tag)) {
				if (enumArray[tag] == null) {
					$('#' + makeId(id, getId(tag), 'input')).val(values[0]);
				} else {
					$('#' + makeId(id, getId(tag), 'select')).val(values[0]);
				}
			}
		});
	}
	
	id = makeId(subjectId, tagId);
	var subjectName = groupName[group-1] + typeCode + countIndex + suffix;
	var textValue = subjectName;
	$('#' + makeId(id, 'input')).val(textValue);
	makeAttributes($('#' + makeId(id, 'input')),
				   'size', textValue.length);
	if (groupType[group-1] == 'Mouse') {
		var id = makeId('Subject', group, groupCounter[group-1]);
		var tag = 'lot#';
		var lot = countIndex - firstMouseId + 1;
		$('#' + makeId(id, getId(tag), 'input')).val(lot);
	}
	enableNavigationButtons(group);
	var headerId = makeId(subjectId, 'header');
	showColumn(group, countIndex, headerId);
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
		id = makeId('Subject', group, groupContainer[group-1], 'container');
		var div = $('#' + id);
		div.remove();
		if (newGroup[groupType[group-1]] != null && newGroup[groupType[group-1]][groupName[group-1]] != null) {
			delete newGroup[groupType[group-1]][groupName[group-1]];
			$('#' + groupType[group-1]).css('display', '');
		}
		if ($.isEmptyObject(allSelectedSubjects) && !existsNewSubjects()) {
			$('#Submit').attr('disabled', 'disabled');
			$('#Debug').attr('disabled', 'disabled');
		}
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
	var subjectGroupName = 'PSOC';
	$('#selectTag').attr('selected', 'selected');
	$('#NewSubject').attr('disabled', 'disabled');
	$('#SelectSubjects').attr('disabled', 'disabled');
	$('#GetSubject').attr('disabled', 'disabled');
	$('#GetSubject').val('Retrieve Subject');
	$('#NewSubject').val('New Subject');
	$('#SelectSubjects').val('Get Subjects List');
	selectSubject(value, subjectGroupName + '-', null, $('#all_subjects'), subjectGroupName);
	if (newGroup[value] == null) {
		newGroup[value] = new Object();
	}
	if (newGroup[value][subjectGroupName + '-'] == null) {
		newGroup[value][subjectGroupName + '-'] = groupCounter.length;
	}
	$('#' + value).css('display', 'none');
	if ($('#Submit').attr('disabled') == 'disabled') {
		$('#Submit').removeAttr('disabled');
		$('#Debug').removeAttr('disabled');
	}
}

function enableSubjectButtons() {
	if ($('#tags').children('option:selected').index() > 0) {
		$('#NewSubject').removeAttr('disabled');
		$('#SelectSubjects').removeAttr('disabled');
		$('#GetSubject').val('Retrieve ' + $('#tags option:selected').text());
		$('#NewSubject').val('New ' + $('#tags option:selected').text());
		$('#SelectSubjects').val('Get ' + getTagTitle($('#tags option:selected').text()) + ' List');
	} else {
		$('#NewSubject').attr('disabled', 'disabled');
		$('#SelectSubjects').attr('disabled', 'disabled');
		$('#GetSubject').attr('disabled', 'disabled');
		$('#GetSubject').val('Retrieve Subject');
		$('#NewSubject').val('New Subject');
		$('#SelectSubjects').val('Get Subjects List');
	}
	$('#subjectsList').empty();
	$('#subjectsList').css('display', 'none');
}

function enableRetrieveButton() {
	if ($('#subjectsList').children('option:selected').index() > 0) {
		$('#NewSubject').attr('disabled', 'disabled');
		$('#SelectSubjects').attr('disabled', 'disabled');
		$('#GetSubject').removeAttr('disabled');
	} else {
		$('#NewSubject').removeAttr('disabled');
		$('#SelectSubjects').removeAttr('disabled');
		$('#GetSubject').attr('disabled', 'disabled');
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
				   'src', resourcePrefix + 'images/' + (toOpen ? 'minus.png' : 'plus.png'),
				   'width', '16',
				   'height', '16',
				   'border', '0',
				   'alt', (toOpen ? '-' : '+'));
	td.append(img);
	td = $('<td>');
	tr.append(td);
	td.html(header);
	var dtId = dt.attr('id');
	window.scrollTo(getLeftOffset(dtId), getTopOffset(dtId));
}

function selectSubject(value, subjectGroupName, suffix, parent, header) {
	var inner = (subjectGroupName == header + '-') ? 'false' : 'true';
	var typeCode ='#';
	if (suffix == null) {
		suffix = '';
	}
	suffix = suffix.replace(/^\s*/, '').replace(/\s*$/, '');
	if (suffix.length > 0) {
		suffix = '-' + suffix;
	}
	groupName.push('PSOC');
	if (inner == 'false') {
		var parts = subjectGroupName.split('#');
		if (parts.length > 1) {
			parts = parts[1].split('-');
			firstSubject = parseInt(parts[0]);
		} else {
			checkForNextSubjectId(value);
		}
	}
	selectedTags.push(new Array());
	groupCounter.push(firstSubject);
	groupContainer.push(firstSubject);
	groupType.push(value);
	if (groupCounter.length == 1) {
		$('#all_subjects').css('display', 'block');
	}
	index = groupCounter.length;

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
				   'onclick', makeFunction('tog', '$(this)', str((inner == 'false' ? getTagTitle(value) : header))),
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
				   'src', resourcePrefix + 'images/' + 'minus.png',
				   'width', '16',
				   'height', '16',
				   'border', '0',
				   'alt', '-');
	td.append(img);
	td = $('<td>');
	tr.append(td);
	td.html(inner == 'false' ? getTagTitle(value) : header);
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
					   'href', 'javascript:' + makeFunction('showColumn', index, firstSubject, str(headerId)));
		a.html(value + ' ' + header + typeCode + firstSubject);
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
	var val = (inner == 'false' ? header + typeCode + firstSubject : subjectGroupName);
	th.html(value + ' ' + val + suffix);
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
	var textValue = val + suffix;
	$('#' + makeId(id, 'input')).val(textValue);
	makeAttributes($('#' + makeId(id, 'input')),
				   'size', textValue.length);
	showColumn(groupCounter.length, firstSubject, headerId);
	return val + suffix;
}

function checkForNextSubjectId(subjectType) {
	firstSubject = 0;
	
	// check if we have already such subjects
	var PREFIX = HOME + '/query/';
	var LIKE = ':like:';
	var SUFFIX = '?limit=none&versions=latest';
	var data_id = 'PSOC#' + '%';
	var subjectId = subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID';
	var url = PREFIX + subjectId + LIKE + encodeURIComponent(data_id) + '(' + subjectId + ')' + SUFFIX;
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: handleSubjectResponse,
		error: handleError
	});
	
	firstSubject += 1;
	subjectMax[subjectType] = firstSubject;
	if (subjectType == 'Mouse') {
		firstMouseId = firstSubject;
	}
}

function handleSubjectResponse(data, textStatus, jqXHR) {
	$.each(data, function(i, object) {
		$.each(object, function(key, value) {
			var index = value.indexOf('#') + 1;
			var val = parseInt(value.substr(index));
			if (val > firstSubject) {
				firstSubject = val;
			}
		});
	});
}

function addTags(group) {
	var value = $('#' + makeId('addtags', group) + ' option:selected').text();
	$('#' + makeId('addTag', group)).attr('selected', 'selected');
	newTags(group, value);
}

function copySubjectTemplate(group, name) {
	var subjectType = groupType[group-1];
	var tagId = subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID'
	var groupsArray = subjectTemplates[subjectType];
	var tags;
	var tagsValues;
	for (var i=groupsArray.length-1; i>=0; i--) {
		var subjectGroup = groupsArray[i];
		if (subjectGroup == group) {
			continue;
		}
		var position = groupCounter[subjectGroup-1];
		var id = makeId('Subject', subjectGroup, position, 'header');
		while ($('#' + id).length == 0 && position >= 1) {
			position--;
		}
		if (position >= 1) {
			tags = getSubjectTags(subjectGroup, position);	
			tagsValues = getSubjectValues(subjectGroup, position, tags);
			break;
		}
	}
	
	// copy the values from the last template
	if (tags != null) {
		var id = makeId('Subject', group, groupCounter[group-1]);
		$.each(tagsValues, function(tag, values) {
			if (!multivalueArray.contains(tag) && tag != tagId) {
				if (enumArray[tag] == null) {
					$('#' + makeId(id, getId(tag), 'input')).val(values[0]);
				} else {
					$('#' + makeId(id, getId(tag), 'select')).val(values[0]);
				}
			}
		});
	}
	if (subjectType == 'Mouse') {
		var id = makeId('Subject', group, groupCounter[group-1]);
		var tag = 'lot#';
		var mouseId = $('#' + makeId(id, getId(tagId), 'input')).val();
		var index = mouseId.indexOf('#') + 1;
		var lot = parseInt(mouseId.substr(index)) - firstMouseId + 1;
		$('#' + makeId(id, getId(tag), 'input')).val(lot);
	}
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
		// get the # for tagMapArray[tagname] 
		if (subjectMax[tagMapArray[tagname]] == null) {
			checkForNextSubjectId(tagMapArray[tagname]);
		} else {
			firstSubject = parseInt(subjectMax[tagMapArray[tagname]]) + 1;
			subjectMax[tagMapArray[tagname]] = firstSubject;
		}
		var name = 'PSOC#' + firstSubject;
		var parent = $('#' + makeId(id, 'button'));
		if (parent.children().size() == 0) {
			var parts = id.split('_');
			var subjectType = groupType[parts[1] - 1];
			var subjectID = makeId('Subject', parts[1], parts[2], subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID', 'input');
			
			value = selectSubject(tagMapArray[tagname], name, '', parent, 'All ' + tagname);
			group = getChild(parent, 1).attr('id').split('_')[1];
			position = firstSubject;
		} else {
			var parts = getChild(parent, 1).attr('id').split('_');
			group = parts[1];
			groupCounter[group-1] = firstSubject-1;
			value = newSubject(group, 'true');
			position = groupCounter[group-1];
			subjectMax[tagMapArray[tagname]] = position;
		}
		if (subjectTemplates[tagMapArray[tagname]] == null) {
			subjectTemplates[tagMapArray[tagname]] = new Array();
		}
		if (!subjectTemplates[tagMapArray[tagname]].contains(group)) {
			subjectTemplates[tagMapArray[tagname]].push(group);
		}
		copySubjectTemplate(group, name);
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
	var headerId = makeId(subjectId, position, 'header');
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
				   'href', 'javascript:' + makeFunction('showColumn', group, position, str(headerId)));
	a.html(groupType[group-1] + ' ' + value);
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
}

function addButtonValue(parent, value, group, position) {
	var subjectId = makeId('Subject', group);
	var headerId = makeId(subjectId, position, 'header');
	var tr = $('<tr>');
	makeAttributes(tr,
				   'class', 'file-tag-list',
				   'id', makeId(subjectId, 'val', position));
	var td = $('<td>');
	makeAttributes(td,
				   'class', 'file-tag multivalue');
	var a = $('<a>');
	makeAttributes(a,
				   'href', 'javascript:' + makeFunction('showColumn', group, position, str(headerId)));
	a.html(groupType[group-1] + ' ' + value);
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
		if (linkArray.contains(tagname)) {
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
var allUpdatedSubjects;
var allDeletedSubjects;
var allNewSubjects;
var totalRequests;
var sentRequests;
var newSubjectsQueue;
var deleteSubjectsQueue;
var addValuesQueue;
var deleteValuesQueue;
var tagsIds;
var isDebug;
var traceBuffer;
var allSelectedSubjects = new Object();
var selectedTagsIds = new Object();
var confirmDeleteSubjectsDialog = $('<div></div>');

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

function init(home, user) {

confirmDeleteSubjectsDialog.dialog({
	autoOpen: false,
	title: 'Do you want to delete the following subject(s)?',
	buttons: {
		"Cancel": function() {
				$(this).dialog('close');
			},
		"OK": function() {
				$(this).dialog('close');
				postSubjects(true);
				expiration_warning = true;
			}
	},
	draggable: true,
	height: 300,
	modal: true,
	resizable: true,
	width: 600
});
	expiration_warning = false;
	HOME = home;
	USER = user;
	$('#psoc_progress_bar').css('display', '');
	$('#Status').html('Initializing the form. Please wait...');
	initTypedef();
	initTagdef();
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
	$('#tags').css('display', '');
	totalRequests = selectArray.length;
	sentRequests = 0;
	drawProgressBar(0);
	displayStatus('sendSelectRequest()');
}

function initTypedef() {
	var url = HOME + '/tags/typedef(typedef;' + encodeURIComponent('typedef values') + ')';
	enumArray = new Object();
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			$.each(data, function(i, object) {
				var typedefValues = object['typedef values'];
				if (typedefValues != null) {
					var values = new Array();
					$.each(typedefValues, function(i, item) {
						var index = item.indexOf(' ') + 1;
						values.push(item.substr(index));
					});
					values.sort();
					enumArray[object.typedef] = values;
				}
			});
		},
		error: handleError
	});
}

function initTagdef() {
	var url = HOME + '/query/view:like:' + encodeURIComponent('%ID') + '(view;' + encodeURIComponent('_cfg_file list tags') + ')';
	allTags = new Array();
	linkArray = new Array();
	dateArray = new Array();
	groupTags = new Array();
	multivalueArray = new Array();
	tagMapArray = new Object();
	tagsArray = new Object();
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			$.each(data, function(i, object) {
				var tags = object['_cfg_file list tags'];
				$.each(tags, function(i, item) {
					if (!allTags.contains(item)) {
						allTags.push(item);
					}
				});
				var view = object.view;
				var entity = view[0].toUpperCase() + view.substr(1, view.length - 3);
				tagsArray[entity] = tags;
				groupTags.push(entity);
			});
		},
		error: handleError
	});
	
	groupTags.sort();
	
	url = HOME + '/tags/tagdef(tagdef;' + encodeURIComponent('tagdef type') + ';' + encodeURIComponent('tagdef multivalue') + ')?limit=none';
	var temp = new Array();
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			$.each(data, function(i, object) {
				if (allTags.contains(object.tagdef)) {
					if (object['tagdef multivalue']) {
						multivalueArray.push(object.tagdef);
					}
					if (object['tagdef type'] == 'date') {
						dateArray.push(object.tagdef);
					} else if (object.tagdef != object['tagdef type'] && object.tagdef + 'ID' != object['tagdef type']) {
						if (allTags.contains(object['tagdef type'])) {
							linkArray.push(object.tagdef);
							var entity = object['tagdef type'];
							tagMapArray[object.tagdef] = entity[0].toUpperCase() + entity.substr(1, entity.length - 3);
						}
					}
				}
			});
		},
		error: handleError
	});
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
	alert(err != null ? decodeURIComponent(err) : jqXHR.responseText);
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
	var subjectType = $('#tags option:selected').text();
	var subjectGroupName = $('#subjectsList option:selected').text();
	$('#subjectsList').empty();
	$('#subjectsList').css('display', 'none');
	$('#Status').css('color', '#33cc33');
	$('#Status').html('Retrieving ' + subjectType + ' "' + subjectGroupName +'". Please wait...');
	setTimeout(function(){retrieveSubject(subjectGroupName)}, 1);
}

function retrieveSubject(subjectGroupName) {
	var subjectType = $('#tags option:selected').text();
	var PREFIX = HOME + '/tags/';
	var SUFFIX = subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID=' + encodeURIComponent(subjectGroupName);
	var url = PREFIX + SUFFIX;
	$('#selectTag').attr('selected', 'selected');
	$('#NewSubject').attr('disabled', 'disabled');
	$('#SelectSubjects').attr('disabled', 'disabled');
	$('#GetSubject').attr('disabled', 'disabled');
	$('#GetSubject').val('Retrieve Subject');
	$('#NewSubject').val('New Subject');
	$('#SelectSubjects').val('Get Subjects List');
	var subject = getSubjectEntity(subjectType, subjectGroupName + '-', url, null, $('#all_subjects'), subjectGroupName, 0, 0);
	var group = subject.group;
	var position = subject.position;
	var headerId = makeId('Subject', group, position, 'header');
	showColumn(group, position, headerId);
	$('#Status').html('');
	$('#Status').css('color', 'black');
	addSeletedSubjects(group);
	$('#Submit').removeAttr('disabled');
	$('#Debug').removeAttr('disabled');
	$('#' + subjectType).css('display', 'none');
}

function compareTagValues(oldArray, newArray) {
	var add = new Array();
	var del = new Array();
	var ret = new Object();
	
	$.each(oldArray, function(i, item) {
		if (!newArray.contains(item)) {
			del.push(item);
		}
	});
	
	$.each(newArray, function(i, item) {
		if (!oldArray.contains(item)) {
			add.push(item);
		}
	});
	
	if (del.length > 0) {
		ret['del'] = del;
	}
	if (add.length > 0) {
		ret['add'] = add;
	}
	
	return ret;
}

function compareSubjectIds(left, right) {
	var leftId = parseInt(left.split('#')[1]);
	var rightId = parseInt(right.split('#')[1]);
	return leftId - rightId;
}

function compareSubjects(oldSubjects, newSubjects) {
	var mod = new Object();
	
	$.each(oldSubjects, function(key, val) {
		if (newSubjects[key] == null) {
			mod[key] = new Object();
			mod[key]['del'] = val;
		}
		 else {
			var res = compareTags(val['values'], newSubjects[key]['values']);
			if (!$.isEmptyObject(res)) {
				mod[key] = new Object();
				mod[key]['mod'] = res;
			}
		}
	});
	
	$.each(newSubjects, function(key, val) {
		if (oldSubjects[key] == null) {
			mod[key] = new Object();
			mod[key]['add'] = val;
		}
	});
	
	return mod;
}

function compareTags(oldTags, newTags) {
	var mod = new Object();

	$.each(oldTags, function(tag, val) {
		if (newTags[tag] == null) {
			mod[tag] = new Object();
			mod[tag]['del'] = val;
		} else {
			var res = compareTagValues(val, newTags[tag]);
			if (!$.isEmptyObject(res)) {
				mod[tag] = new Object();
				if (!multivalueArray.contains(tag)) {
					mod[tag]['add'] = res['add'];
				} else {
					if (res['del'] != null) {
						mod[tag]['del'] = res['del'];
					}
					if (res['add'] != null) {
						mod[tag]['add'] = res['add'];
					}
				}
			}
		}
	});
	
	$.each(newTags, function(tag, val) {
		if (oldTags[tag] == null) {
			mod[tag] = new Object();
			mod[tag]['add'] = val;
		}
	});
	
	return mod;
}

function selectSubjects() {
	var subjectType = $('#tags option:selected').text();
	var idTag = subjectType.substr(0,1).toLowerCase() + subjectType.substr(1) + 'ID';
	var PREFIX = HOME + '/query/';
	var SUFFIX = encodeURIComponent(idTag) + ':like:' + encodeURIComponent('PSOC%') + '(' + encodeURIComponent(idTag) + ')';
	var url = PREFIX + SUFFIX;
	var subjects = new Array();
	$.ajax({
		url: url,
		accepts: {text: 'application/json'},
		dataType: 'json',
		headers: {'User-agent': 'Tagfiler/1.0'},
		async: false,
		success: function(data, textStatus, jqXHR) {
			$.each(data, function(i, object) {
				subjects.push(object[idTag]);
			});
		},
		error: handleError
	});
	subjects.sort();
	var select = $('#subjectsList');
	var option = $('<option>');
	makeAttributes(option,
				   'id', 'selectSubject',
				   'value', 'Choose a Subject');
	option.text('Choose ' + $('#tags option:selected').text());
	select.append(option);
	for (var i=0; i < subjects.length; i++) {
		option = $('<option>');
		makeAttributes(option,
					   'id', 'selectSubject' + (i + 1),
					   'value', subjects[i]);
		option.text(subjects[i]);
		select.append(option);
	}
	$('#subjectsList').css('display', '');
	$('#NewSubject').attr('disabled', 'disabled');
	$('#SelectSubjects').attr('disabled', 'disabled');
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

	// collapse the subject
	$('#' + makeId('Subject', group, 'span')).click();
	
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
									$('#' + id).html(subjectType + ' ' + val);
									id = makeId('Subject', group, 'val', position);
									var tr = $('#' + id);
									var td = getChild(tr, 1);
									var a = getChild(td, 1);
									a.html(subjectType + ' ' + val);
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
										val.sort(compareSubjectIds);
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
											var parts = value.split('-');
											var countIndex = parseInt(parts[parts.length-1]);
											if (countIndex > arrayPosition) {
												groupCounter[arrayGroup-1] = countIndex;
											}
											addButtonValue($('#' + makeId(id, 'button', 'entity')), value, arrayGroup, arrayPosition);
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
								} else if (td.is('SELECT') || td.is('INPUT')) {
									td.val(val);
								}
							}
						});
					});
				},
		error: handleError
	});
	
	return {group: group, position: position};
}

function getPredicate(subjects, subject) {
	var predicate = getPredicateParts(subjects, subject);	
	return predicate.tag + '=' + predicate.val;
}

function getPredicateParts(subjects, subject) {
	var values = subjects[subject].values;
	var predicate;
	$.each(values, function(tag, tagval) {
		predicate = {tag: tag, val: tagval};
		return false;
	});
	
	return predicate;
}

function submitForm() {
	getAllSubjects();
	var mod = compareSubjects(allSelectedSubjects, allSubjects);
	$.each(mod, function(subject, value) {
		$.each(value, function(action, tags) {
			if (action == 'mod') {
				$.each(tags, function(tag, tagActions) {
					$.each(tagActions, function(tagAction, values) {
						if (tagAction == 'add' && !addValuesQueue.contains(subject)) {
							addValuesQueue.push(subject);
						} else if (tagAction == 'del' && !linkArray.contains(tag) && !deleteValuesQueue.contains(subject)) {
							deleteValuesQueue.push(subject);
						}
					});
				});
				var predicate = getPredicateParts(allSelectedSubjects, subject);
				allUpdatedSubjects[subject] = new Object();
				allUpdatedSubjects[subject]['mod'] = tags;
				allUpdatedSubjects[subject]['values'] = new Object();
				allUpdatedSubjects[subject]['values'][predicate.tag] = predicate.val;
			} else if (action == 'add') {
				allNewSubjects[subject] = tags;
			} else if (action == 'del') {
				deleteSubjectsQueue.push(subject);
				var predicate = getPredicateParts(allSelectedSubjects, subject);
				allDeletedSubjects[subject] = new Object();
				allDeletedSubjects[subject]['values'] = new Object();
				allDeletedSubjects[subject]['values'][predicate.tag] = predicate.val;
			}
		});
	});
	confirmPostSubjects();
}

function debugForm() {
	traceBuffer = '\n********************\n';
	traceBuffer += 'Retrieved subjects *\n';
	traceBuffer += '********************\n\n';
	displaySubjects(allSelectedSubjects);
	traceBuffer += '\n****************\n';
	traceBuffer += 'Saved subjects *\n';
	traceBuffer += '****************\n\n';
	getAllSubjects();
	displaySubjects(allSubjects);
	
	traceBuffer += '\n*********\n';
	traceBuffer += 'Actions *\n';
	traceBuffer += '*********\n\n';
	
	var mod = compareSubjects(allSelectedSubjects, allSubjects);
	$.each(mod, function(subject, value) {
		$.each(value, function(action, tags) {
			if (action == 'mod') {
				traceBuffer += 'Subject: ' + getPredicate(allSubjects, subject) + '\n';
				traceBuffer += '\tAction: ' + action + '\n';
				$.each(tags, function(tag, tagActions) {
					traceBuffer += '\t\tTag: ' + tag + '\n';
					$.each(tagActions, function(tagAction, values) {
						traceBuffer += '\t\t\t' + tagAction + ': ' + values.join(',') + '\n';
						if (tagAction == 'add' && !addValuesQueue.contains(subject)) {
							addValuesQueue.push(subject);
						} else if (tagAction == 'del' && !linkArray.contains(tag) && !deleteValuesQueue.contains(subject)) {
							deleteValuesQueue.push(subject);
						}
					});
				});
				var predicate = getPredicateParts(allSelectedSubjects, subject);
				allUpdatedSubjects[subject] = new Object();
				allUpdatedSubjects[subject]['mod'] = tags;
				allUpdatedSubjects[subject]['values'] = new Object();
				allUpdatedSubjects[subject]['values'][predicate.tag] = predicate.val;
			} else if (action == 'add') {
				allNewSubjects[subject] = tags;
				traceBuffer += 'Subject: ' + getPredicate(allSubjects, subject) + '\n';
				traceBuffer += '\tAction: ' + action + '\n';
				$.each(tags, function(key, items) {
					$.each(items, function(tag, values) {
						traceBuffer += '\t\t' + tag + '=[' + values.join(',') + ']\n';
					});
				});
			} else if (action == 'del') {
				traceBuffer += 'Subject: ' + getPredicate(allSelectedSubjects, subject) + '\n';
				traceBuffer += '\tAction: ' + action + '\n';
				deleteSubjectsQueue.push(subject);
				var predicate = getPredicateParts(allSelectedSubjects, subject);
				allDeletedSubjects[subject] = new Object();
				allDeletedSubjects[subject]['values'] = new Object();
				allDeletedSubjects[subject]['values'][predicate.tag] = predicate.val;
			}
		});
	});
	
	traceBuffer += '\n***************\n';
	traceBuffer += 'HTTP Requests *\n';
	traceBuffer += '***************\n\n';
	
	postSubjects(false);
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
	var result = new Object();
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
						var index = value.indexOf(' ') + 1;
						values.push(value.substr(index));
					}
					result[tags[i]] = values;
				}
			}
		}
	}
	return result;
}

function getAllSubjects() {
	allSubjects = new Object();
	allNewSubjects = new Object();
	allDeletedSubjects = new Object();
	allUpdatedSubjects = new Object();
	tagsIds = new Object();
	newSubjectsQueue = new Array();
	deleteSubjectsQueue = new Array();
	addValuesQueue = new Array();
	deleteValuesQueue = new Array();
	var tags;
	for (var i=0; i < groupCounter.length; i++) {
		tags = null;
		for (var j=1; j<=groupCounter[i]; j++) {
			var id = makeId('Subject', i+1, j);
			if ($('#' + id).length != 0) {
				if (tags == null) {
					tags = getSubjectTags(i+1, j);
				}
				var subjectTags = new Object();
				subjectTags['values'] = getSubjectValues(i+1, j, tags);
				allSubjects[id] = subjectTags;
				if (tagsIds[tags[0]] == null) {
					tagsIds[tags[0]] = new Object();
				}
				tagsIds[tags[0]][subjectTags['values'][tags[0]]] = id;
			}
		}
	}
}

function existsNewSubjects() {
	for (var i=0; i < groupCounter.length; i++) {
		for (var j=1; j<=groupCounter[i]; j++) {
			var id = makeId('Subject', i+1, j);
			if ($('#' + id).length != 0) {
				return true;
			}
		}
	}
	return false;
}

function addSeletedSubjects(group) {
	var tags;
	for (var i=group-1; i < groupCounter.length; i++) {
		tags = null;
		for (var j=1; j<=groupCounter[i]; j++) {
			var id = makeId('Subject', i+1, j);
			if ($('#' + id).length != 0) {
				if (tags == null) {
					tags = getSubjectTags(i+1, j);
				}
				var subjectTags = new Object();
				subjectTags['values'] = getSubjectValues(i+1, j, tags);
				allSelectedSubjects[id] = subjectTags;
				if (selectedTagsIds[tags[0]] == null) {
					selectedTagsIds[tags[0]] = new Object();
				}
				selectedTagsIds[tags[0]][subjectTags['values'][tags[0]]] = id;
			}
		}
	}
}

function displaySubjects(subjects) {
	$.each(subjects, function(subject, val) {
		var values = val['values'];
		traceBuffer += subject + '\n';
		$.each(values, function(value, tagValues) {
			traceBuffer += '\t' + value + ':\n';
			for (var i=0; i<tagValues.length; i++) {
				traceBuffer += '\t\t' + tagValues[i] + '\n';
			}
		});
		traceBuffer += '\n';
	});
	$('#AllBody').css('display', '');
}

function postSubjects(executeRequest) {
	isDebug = !executeRequest;
	$('#psoc_progress_bar').css('display', '');
	resolveDependencies();
	totalRequests = deleteSubjectsQueue.length + newSubjectsQueue.length + deleteValuesQueue.length + addValuesQueue.length;
	sentRequests = 0;
	$('#Status').html('Saving the form. Please wait...');
	$('#Error').html('');
	if (deleteSubjectsQueue.length > 0) {
		displayStatus('submitDelete()');
	} else if (newSubjectsQueue.length > 0) {
		displayStatus('submitCreate()');
	} else if (deleteValuesQueue.length > 0) {
		displayStatus('submitDeleteValues()');
	} else if (addValuesQueue.length > 0) {
		displayStatus('submitAddValues()');
	} else {
		alert('No changes. Nothing to do.');
		$('#psoc_progress_bar').css('display', 'none');
		$('#Status').html('');
	}
}

function submitDelete() {
	// DELETE a subject
	var url = HOME + '/subject/';
	var values = allDeletedSubjects[deleteSubjectsQueue[sentRequests]]['values'];
	var tags = new Array();
	$.each(values, function(value, tagValues) {
		var tag = encodeURIComponent(value) + '=';
		var tagVals = new Array();
		for (var i=0; i<tagValues.length; i++) {
			tagVals.push(encodeURIComponent(tagValues[i]));
		}
		tags.push(encodeURIComponent(value) + '=' + tagVals.join(','));
	});
	url += tags.join('&');
	drawProgressBar(Math.ceil((sentRequests + 1) * 100 / totalRequests));
	if (isDebug) {
		traceBuffer += 'DELETE ' + url + '\n';
		handleSubmitResponse();
	} else {
		$.ajax({
			url: url,
			type: 'DELETE',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: false,
			success: handleSubmitResponse,
			error: handleSubmitError
		});
	}
}

function submitCreate() {
	// POST the subject
	var url = HOME + '/subject/?incomplete&';
	var values = allNewSubjects[newSubjectsQueue[sentRequests-deleteSubjectsQueue.length]]['values'];
	var tags = new Array();
	$.each(values, function(value, tagValues) {
		var tag = encodeURIComponent(value) + '=';
		var tagVals = new Array();
		for (var i=0; i<tagValues.length; i++) {
			tagVals.push(encodeURIComponent(tagValues[i]));
		}
		tags.push(encodeURIComponent(value) + '=' + tagVals.join(','));
	});
	url += tags.join('&');
	drawProgressBar(Math.ceil((sentRequests + 1) * 100 / totalRequests));
	if (isDebug) {
		traceBuffer += 'POST ' + url + '\n';
		handleSubmitResponse();
	} else {
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
}

function submitDeleteValues() {
	// DELETE subject values
	var subject = deleteValuesQueue[sentRequests-deleteSubjectsQueue.length-newSubjectsQueue.length];
	var predicate = getPredicateParts(allSubjects, subject);
	var url = HOME + '/tags/' + encodeURIComponent(predicate.tag) + '=' + encodeURIComponent(predicate.val);
	var values = allUpdatedSubjects[subject]['mod'];
	var tags = new Array();
	$.each(values, function(value, actions) {
		var tagValues = actions.del;
		if (tagValues != null) {
			var tagVals = new Array();
			var tag = encodeURIComponent(value) + '=';
			for (var i=0; i<tagValues.length; i++) {
				tagVals.push(encodeURIComponent(tagValues[i]));
			}
			tags.push(encodeURIComponent(value) + '=' + tagVals.join(','));
		}
	});
	url += '(' + tags.join(';') + ')';
	drawProgressBar(Math.ceil((sentRequests + 1) * 100 / totalRequests));
	if (isDebug) {
		traceBuffer += 'DELETE ' + url + '\n';
		handleSubmitResponse();
	} else {
		$.ajax({
			url: url,
			type: 'DELETE',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: false,
			success: handleSubmitResponse,
			error: handleSubmitError
		});
	}
}

function submitAddValues() {
	// PUT subject values
	var subject = addValuesQueue[sentRequests-deleteSubjectsQueue.length-newSubjectsQueue.length-deleteValuesQueue.length];
	var predicate = getPredicateParts(allSubjects, subject);
	var url = HOME + '/tags/' + encodeURIComponent(predicate.tag) + '=' + encodeURIComponent(predicate.val);
	var values = allUpdatedSubjects[subject]['mod'];
	var tags = new Array();
	$.each(values, function(value, actions) {
		var tagValues = actions.add;
		if (tagValues != null) {
			var tagVals = new Array();
			var tag = encodeURIComponent(value) + '=';
			for (var i=0; i<tagValues.length; i++) {
				tagVals.push(encodeURIComponent(tagValues[i]));
			}
			tags.push(encodeURIComponent(value) + '=' + tagVals.join(','));
		}
	});
	url += '(' + tags.join(';') + ')';
	drawProgressBar(Math.ceil((sentRequests + 1) * 100 / totalRequests));
	if (isDebug) {
		traceBuffer += 'PUT ' + url + '\n';
		handleSubmitResponse();
	} else {
		$.ajax({
			url: url,
			type: 'PUT',
			headers: {'User-agent': 'Tagfiler/1.0'},
			async: false,
			success: handleSubmitResponse,
			error: handleSubmitError
		});
	}
}

function handleSubmitResponse(data, textStatus, jqXHR) {
	if (++sentRequests >= totalRequests) {
		$('#psoc_progress_bar').css('display', 'none');
		$('#Status').html('');
		listCompleteSubjects();
		if (deleteSubjectsQueue.length > 0) {
			listSubjects(allDeletedSubjects, 'Deleted');
		}
		if (newSubjectsQueue.length > 0) {
			listSubjects(allNewSubjects, 'Created');
		}
		if (!$.isEmptyObject(allUpdatedSubjects)) {
			listSubjects(allUpdatedSubjects, 'Modified');
		}
		$('#AllBody').val(traceBuffer);
		$('#AllBody').prop('scrollTop',  $('#AllBody').prop('scrollHeight'));
		window.scrollTo(0, $('body').height());
	} else {
		var code;
		if (sentRequests < deleteSubjectsQueue.length) {
			code = 'submitDelete()';
		} else if (sentRequests < deleteSubjectsQueue.length + newSubjectsQueue.length) {
			code = 'submitCreate()';
		} else if (sentRequests < deleteSubjectsQueue.length + newSubjectsQueue.length + deleteValuesQueue.length) {
			code = 'submitDeleteValues()';
		} else {
			code = 'submitAddValues()';
		}
		displayStatus(code);
	}
}

function handleSubmitError(jqXHR, textStatus, errorThrown) {
	var p = $('<p>');
	$('#Error').append(p);
	p.html('ERROR: ' + errorThrown);
	var err = jqXHR.getResponseHeader('X-Error-Description');
	p = $('<p>');
	$('#Error').append(p);
	p.html(err != null ? decodeURIComponent(err) : jqXHR.responseText);
	$('#psoc_progress_bar').css('display', 'none');
	$('#Status').html('');
}

function resolveDependencies() {
	$.each(allNewSubjects, function(subject, val) {
		if (!newSubjectsQueue.contains(subject)) {
			addToNewSubjectsQueue(subject);
		}
	});
}

function addToNewSubjectsQueue(subject) {
	var values = allNewSubjects[subject]['values'];
	var first = true;
	$.each(values, function(value, tagValues) {
		if (first) {
			first = false;
		} else if (tagsMap[value] != null) {
			var mapValue = tagsMap[value];
			for (var i=0; i<tagValues.length; i++) {
				if (tagsIds[mapValue] != null && tagsIds[mapValue][tagValues[i]] != null) {
					addToNewSubjectsQueue(tagsIds[mapValue][tagValues[i]]);
				}
			}
		}
	});
	if (!newSubjectsQueue.contains(subject)) {
		newSubjectsQueue.push(subject);
	}
}

function listCompleteSubjects() {
	if (isDebug) {
		traceBuffer += '\n***********************************\n';
		traceBuffer += 'Summary of the subjects proceeded *\n';
		traceBuffer += '***********************************\n\n';
	} else {
		var ul = $('<ul>').attr({id: 'completedSubjects'});
		var psoc = $('#psoc');
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
		b.html('All subjects were successfully proceeded.');
		p = $('<p>');
		psoc.append(p);
		p.html('See below for a summary of the subjects.');
		psoc.append(ul);
	}
}

function listSubjects(subjects, title) {
	if (isDebug) {
		traceBuffer += title + '\n';
		$.each(subjects, function(subject, val) {
			traceBuffer += '\t' + getPredicate(subjects, subject) + '\n';
		});
	} else {
		var ul = $('<ul>');
		$.each(subjects, function(subject, val) {
			var li = $('<li>');
			li.html(getPredicate(subjects, subject));
			ul.append(li);
		});
		var li = $('<li>').html(title);
		li.append(ul);
		$('#completedSubjects').append(li);
	}
}

function confirmPostSubjects() {
	var deletedSubjects = new Array();
	$.each(allDeletedSubjects, function(subject, val) {
		deletedSubjects.push('\t' + getPredicate(allDeletedSubjects, subject));
	});
	if (deletedSubjects.length > 0) {
		confirmDeleteSubjectsDialog.html(deletedSubjects.join('<br/>'));
		confirmDeleteSubjectsDialog.dialog('open');
	} else {
		postSubjects(true);
		expiration_warning = true;
	}
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

function viewBody() {
	$('#AllBody').val($('body').html());
	$('#AllBody').css('display', '');
	$('#viewBody').attr('disabled', 'disabled');
	$('#hideBody').removeAttr('disabled');
	window.scrollTo(0, $('body').height());
}

function hideBody() {
	$('#AllBody').css('display', 'none');
	$('#hideBody').attr('disabled', 'disabled');
	$('#viewBody').removeAttr('disabled');
}
