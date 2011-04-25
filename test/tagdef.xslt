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
<xsl:template match="//tr">
  <xsl:if test="@class='tagdef writeok' or @class='tagdef readonly'">
    <xsl:text>( </xsl:text>
    <xsl:for-each select="td">
      <xsl:text>'</xsl:text> <xsl:value-of select="." /><xsl:text>' </xsl:text>
    </xsl:for-each>
    <xsl:text>)
    </xsl:text>
  </xsl:if>
  <xsl:if test="@class='heading'">
    <xsl:text>
    </xsl:text>
  </xsl:if>
</xsl:template>
</xsl:stylesheet>

