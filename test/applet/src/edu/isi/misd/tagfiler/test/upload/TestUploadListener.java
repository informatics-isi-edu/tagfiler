package edu.isi.misd.tagfiler.test.upload;

import edu.isi.misd.tagfiler.test.TagfilerClient;
import edu.isi.misd.tagfiler.test.TestListener;
import edu.isi.misd.tagfiler.upload.FileUploadListener;

/**
 * Class to simulate a GUI listener
 * 
 * @author Serban Voinea
 *
 */
public class TestUploadListener extends TestListener implements FileUploadListener {
	
	public TestUploadListener(Object lock, TagfilerClient client, boolean enableChecksum) {
		super(lock, client, enableChecksum);
	}

	@Override
	public void notifyFailure(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("Failure: " + arg0 + ".");
		notifyEndOfTest();
		
	}

	@Override
	public void notifyFailure(String arg0, String arg1) {
		// TODO Auto-generated method stub
		System.out.println("Failure: " + arg0 + ", " + arg1 + ".");
		notifyEndOfTest();
		
	}
	

}
