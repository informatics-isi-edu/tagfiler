package edu.isi.misd.tagfiler.test.download;

import edu.isi.misd.tagfiler.TagFilerDownloadApplet;

/**
 * Class to simulate an applet
 * 
 * @author Serban Voinea
 *
 */
public class TestDownloadApplet extends TagFilerDownloadApplet {

    private static final long serialVersionUID = 2134123;

    public TestDownloadApplet(int maxConnections, int socketBufferSize, boolean allowChunks, int appletChunkSize) {
		this.maxConnections = maxConnections;
		this.socketBufferSize = socketBufferSize;
		this.allowChunks = allowChunks;
		this.chunkSize = appletChunkSize;
	}
	
    /**
     * Convenience method for evaluating a JS function
     * 
     * @param function
     * 			the function to be evaluated
     * @param arg
     * 			the function argument
     */
    public void eval(String function, String arg) {
    }
}
