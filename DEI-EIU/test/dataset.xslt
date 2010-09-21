<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/">
  <xsl:for-each select="//fieldset">
	<xsl:text>
	</xsl:text>
	<xsl:value-of select="legend" />: <xsl:for-each select="form"> <xsl:value-of select="input[2]/@value" /><xsl:text>        </xsl:text></xsl:for-each>
  </xsl:for-each>
</xsl:template>
</xsl:stylesheet>

