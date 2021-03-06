<?xml version="1.0" encoding="ISO-8859-1"?>
<!--
Copyright 2010 University of Southern California

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="head">
</xsl:template>
<xsl:template match="script">
</xsl:template>
<xsl:template match="h2">
</xsl:template>
<xsl:template match="h1">
</xsl:template>
<xsl:template match="p">
</xsl:template>
<xsl:template match="th">
</xsl:template>
<xsl:template match="input">
</xsl:template>
<xsl:template match="//table[@class='topmenu']">
</xsl:template>
<xsl:template match="td//td">
  <xsl:if test="@class='file-tag readusers multivalue'">
    <xsl:text>read users: ( '</xsl:text><xsl:value-of select="normalize-space(.)" /><xsl:text>' )</xsl:text>
  </xsl:if>
  <xsl:if test="@class='file-tag writeusers multivalue'">
    <xsl:text>write users: ( '</xsl:text><xsl:value-of select="normalize-space(.)" /><xsl:text>' )</xsl:text>
  </xsl:if>
</xsl:template>
<xsl:template match="td[@class='tag name']">
</xsl:template>
<xsl:template match="td[@class='file-tag tagdefmultivalue']">
</xsl:template>
</xsl:stylesheet>

