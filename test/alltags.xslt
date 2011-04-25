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
<xsl:strip-space elements="*"/>
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
<xsl:template match="td">
  <xsl:choose>
  <xsl:when test="@class='tag name'">
    <xsl:value-of select="normalize-space(.)" /><xsl:text>: ( </xsl:text>
  </xsl:when>
  <xsl:otherwise>
    <xsl:for-each select="table/tr/td">
      <xsl:if test="table/tr/td/a">
        <xsl:if test="normalize-space(.)!=''">
          <xsl:text>'</xsl:text><xsl:value-of select="normalize-space(table/tr/td/a)" /><xsl:text>' </xsl:text>
        </xsl:if>
      </xsl:if>
      <xsl:if test="not(table/tr/td/a)">
        <xsl:if test="normalize-space(.)!=''">
          <xsl:text>'</xsl:text><xsl:value-of select="normalize-space(.)" /><xsl:text>' </xsl:text>
        </xsl:if>
      </xsl:if>
    </xsl:for-each>
    <xsl:for-each select="table/tr/form/td">
        <xsl:if test="text()">
          <xsl:text>'</xsl:text><xsl:value-of select="normalize-space(.)" /><xsl:text>' </xsl:text>
        </xsl:if>
    </xsl:for-each>
    <xsl:text>)
    </xsl:text>
  </xsl:otherwise>
  </xsl:choose>
</xsl:template>
</xsl:stylesheet>

