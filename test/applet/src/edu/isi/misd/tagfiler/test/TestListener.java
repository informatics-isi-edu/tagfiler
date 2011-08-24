package edu.isi.misd.tagfiler.test;

import edu.isi.misd.tagfiler.ui.FileListener;

/**
 * Class to simulate a GUI listener
 * 
 * @author Serban Voinea
 *
 */
public class TestListener implements FileListener {
	
	int totalFiles;

	int transferedFile;
	
	long totalBytes;

	long transferedBytes;
	
	Object lock;
	
	TagfilerClient client;
	
	boolean enableChecksum;
	
	public TestListener(Object lock, TagfilerClient client, boolean enableChecksum) {
		
		this.lock = lock;
		this.client = client;
		this.enableChecksum = enableChecksum;
	}
	
	protected void notifyEndOfTest() {
		synchronized (lock) {
			client.setReady(true);
			lock.notifyAll();
		}
	}
	@Override
	public void notifyChunkTransfered(boolean arg0, long arg1) {
		// TODO Auto-generated method stub
		transferedBytes += enableChecksum ? arg1/2 : arg1;
		System.out.print("\rTransfering " + (transferedFile + 1) + " of " + totalFiles + " file(s) (" + 
				transferedBytes + " bytes of "+ totalBytes + " bytes).");

		if (arg0) {
			transferedFile++;
		}
	}

	@Override
	public void notifyError(Throwable arg0) {
		// TODO Auto-generated method stub
		System.out.println("Error: " + arg0.getMessage() + ".");
		arg0.printStackTrace();
		notifyEndOfTest();

	}

	@Override
	public void notifyFileTransferComplete(String arg0, long arg1) {
		// TODO Auto-generated method stub
		notifyChunkTransfered(true, arg1);

	}

	@Override
	public void notifyFileTransferSkip(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("File Transfer Skipped: " + arg0 + ".");

	}

	@Override
	public void notifyFileTransferStart(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("File Transfer Started: " + arg0 + ".");

	}

	@Override
	public void notifyLogMessage(String arg0) {
		// TODO Auto-generated method stub
		System.out.println("Log Message: " + arg0 + ".");

	}

	@Override
	public void notifyStart(String arg0, long arg1) {
		// TODO Auto-generated method stub
		System.out.println("Transfer started for dataset: " + arg0 + ", Total bytes: " + arg1 + ".");

	}

	@Override
	public void notifySuccess(String arg0, int version) {
		// TODO Auto-generated method stub
		System.out.println("Success for dataset: " + arg0 + ".");
		notifyEndOfTest();

	}

	public void setTotalFiles(int totalFiles) {
		this.totalFiles = totalFiles;
	}

	public int getTotalFiles() {
		return totalFiles;
	}

	public void setTotalBytes(long totalBytes) {
		this.totalBytes = totalBytes;
	}

	public long getTotalBytes() {
		return totalBytes;
	}

	@Override
	public void notifyFatal(Throwable arg0) {
		// TODO Auto-generated method stub
		System.out.println("Fatal error: " + arg0.getMessage() + ".");
		arg0.printStackTrace();
		notifyEndOfTest();
		
	}

	@Override
	public void notifyFailure(String arg0, int arg1, String arg2) {
		// TODO Auto-generated method stub
		// TODO Auto-generated method stub
		System.out.println("Failure: " + arg0 + ", Code Error: " + arg1 + " - " + arg2 + ".");
		notifyEndOfTest();
		
	}

	@Override
	public int getFilesCompleted() {
		// TODO Auto-generated method stub
		return 0;
	}

}
