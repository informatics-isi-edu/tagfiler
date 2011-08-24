package edu.isi.misd.tagfiler.test.upload;

import edu.isi.misd.tagfiler.TagFilerUploadApplet;

/**
 * Class to simulate an applet
 * 
 * @author Serban Voinea
 *
 */
public class TestUploadApplet extends TagFilerUploadApplet {

    private static final long serialVersionUID = 2134123;

    public TestUploadApplet(int maxConnections, int socketBufferSize, boolean allowChunks, int appletChunkSize) {
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
	@Override
    public void eval(String function, String arg) {
    }
    
    /**
     * Convenience method for updating the status label
     * 
     * @param status
     */
	@Override
    public void updateStatus(String status) {
    }
    
}
