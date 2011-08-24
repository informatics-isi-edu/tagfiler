package edu.isi.misd.tagfiler.test.download;

import edu.isi.misd.tagfiler.download.FileDownloadListener;
import edu.isi.misd.tagfiler.test.TagfilerClient;
import edu.isi.misd.tagfiler.test.TestListener;

/**
 * Class to simulate a GUI listener
 * 
 * @author Serban Voinea
 *
 */
public class TestDownloadListener extends TestListener implements FileDownloadListener {
	
	public TestDownloadListener(Object lock, TagfilerClient client, boolean enableChecksum) {
		super(lock, client, enableChecksum);
	}
	
	@Override
	public void notifyFailure(String arg0, String arg1) {
		// TODO Auto-generated method stub
		System.out.println("Failure: " + arg0 + ", " + arg1 + ".");
		notifyEndOfTest();

	}

	@Override
	public void notifyFileRetrieveComplete(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("Retrieve completed: " + arg0 + ".");

	}

	@Override
	public void notifyRetrieveStart(int arg0) {
		// TODO Auto-generated method stub
		System.out.println("Retrieve started for: " + arg0 + " file(s).");
		if (arg0 == 0) {
			notifyEndOfTest();
		}

	}

	@Override
	public void notifyUpdateComplete(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("Update completed for dataset: " + arg0 + ".");

	}

	@Override
	public void notifyUpdateStart(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("Update started for dataset: " + arg0 + ".");

	}

}
