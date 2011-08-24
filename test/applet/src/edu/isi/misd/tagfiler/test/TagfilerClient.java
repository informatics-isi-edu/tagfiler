/**
 * 
 */
package edu.isi.misd.tagfiler.test;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FilenameFilter;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import edu.isi.misd.tagfiler.test.download.TestDownloadApplet;
import edu.isi.misd.tagfiler.test.download.TestDownloadListener;
import edu.isi.misd.tagfiler.test.download.TestFileDownloadImplementation;
import edu.isi.misd.tagfiler.test.upload.TestFileUploadImplementation;
import edu.isi.misd.tagfiler.test.upload.TestUploadApplet;
import edu.isi.misd.tagfiler.test.upload.TestUploadListener;
import edu.isi.misd.tagfiler.ui.CustomTagMap;
import edu.isi.misd.tagfiler.ui.CustomTagMapImplementation;
import edu.isi.misd.tagfiler.util.DatasetUtils;

/**
 * Class to test the tagfiler
 * 
 * @author Serban Voinea
 *
 */
public class TagfilerClient {

	private int maxConnections;
	
	private String user;
	
	private String password;
	
	private String serverURL;
	
	private String host;
	
	private String outputDir;
	
	private String direction = "upload";
	
	private String controlNumber;
	
	private int socketBufferSize = 8192;
	
	private int appletChunkSize = 1048576;
	
	private CustomTagMap tagMap = new CustomTagMapImplementation();
	
	private Object lock = new Object();
	
	private boolean ready;
	
	private boolean enableChecksum = false;
	
	private boolean allowChunks = true;
	
	private long elapsed = 1;
	
	private long datasetSize;
	
	/**
     * Excludes "." and ".." from directory lists in case the client is
     * UNIX-based.
     */
    private static final FilenameFilter excludeDirFilter = new FilenameFilter() {
        public boolean accept(File dir, String name) {
            return (!name.equals(".") && !name.equals(".."));
        }
    };

	/**
	 * @param args
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		
		//testDigest();
		TagfilerClient client = new TagfilerClient();
		
		int i = 0;
		String arg;
		
		while (i < args.length && args[i].startsWith("-")) {
			arg = args[i++];
			
			if (arg.equals("-a")) {
				if (i < args.length) {
					client.appletChunkSize = Integer.parseInt(args[i++]);
				}
			} else if (arg.equals("-b")) {
				if (i < args.length) {
					client.socketBufferSize = Integer.parseInt(args[i++]);
				}
			} else if (arg.equals("-c")) {
				if (i < args.length) {
					client.maxConnections = Integer.parseInt(args[i++]);
				}
			} else if (arg.equals("-e")) {
				client.enableChecksum = true;
			} else if (arg.equals("-f")) {
				client.allowChunks = false;
			} else if (arg.equals("-h")) {
				if (i < args.length) {
					client.host = args[i++];
					client.serverURL = "https://" + client.host + "/tagfiler";
				}
			} else if (arg.equals("-n")) {
				if (i < args.length) {
					client.controlNumber = args[i++];
					client.direction = "download";
				}
			} else if (arg.equals("-o")) {
				if (i < args.length) {
					client.outputDir = args[i++];
				}
			} else if (arg.equals("-p")) {
				if (i < args.length) {
					client.password = args[i++];
				}
			} else if (arg.equals("-u")) {
				if (i < args.length) {
					client.user = args[i++];
				}
			} 
		}
		
		if (client.direction.equals("download")) {
			//client.tagMap.setValue("Modality", "");
			//client.tagMap.setValue("Study Date", "");
			//client.tagMap.setValue("Study Name", "");
			//client.tagMap.setValue("Study Participant", "");
			client.download();
			System.out.println("Elapsed time: " + client.elapsed + " ms");
	        System.out.println("Download rate: " + DatasetUtils.roundTwoDecimals(((double) client.datasetSize)/1000/client.elapsed) + " MB/s.");
		} else {
			//client.tagMap.setValue("Modality", "fundus");
			//client.tagMap.setValue("Study Date", "2011-01-03");
			//client.tagMap.setValue("Study Name", "CHES");
			//client.tagMap.setValue("Study Participant", "5GB");
			client.upload();
			System.out.println("Elapsed time: " + client.elapsed + " ms");
	        System.out.println("Upload rate: " + DatasetUtils.roundTwoDecimals(((double) client.datasetSize)/1000/client.elapsed) + " MB/s.");
		}
		System.exit(0);

	}
	
	private void upload() {
		System.out.println("Upload serverURL: " + serverURL);
		TestUploadListener tl = new TestUploadListener(lock, this, enableChecksum);
		TestFileUploadImplementation fi = new TestFileUploadImplementation(serverURL, 
				tl, "", tagMap, new TestUploadApplet(maxConnections, socketBufferSize, allowChunks, appletChunkSize), user, password);
		List<String> files = getFiles(new File(outputDir));
		fi.setBaseDirectory(outputDir);
		tl.setTotalFiles(files.size());
		tl.setTotalBytes(getBytes(files));
		datasetSize = tl.getTotalBytes();
		fi.setEnableChecksum(enableChecksum);
		long start = System.currentTimeMillis();
		fi.postFileData(files, "all");
		synchronized (lock) {
			while (!ready) {
				try {
					lock.wait();
				} catch (InterruptedException e) {
					// TODO Auto-generated catch block
					e.printStackTrace();
				}
			}
		}
		
		elapsed = System.currentTimeMillis() - start;
	}
	
    /**
     * Get recursively the files of a directory
     * 
     * @param dir
     *            the directory
     * @return the list with the files names
     */
    private List<String> getFiles(File dir) {
        if (dir == null) throw new IllegalArgumentException(""+dir);
        List<String> files = new ArrayList<String>();
        File[] children = dir.listFiles(excludeDirFilter);
        
        for (int i = 0; i < children.length; i++) {
            if (children[i].isDirectory()) {
            	files.addAll(getFiles(children[i]));
            } else if (children[i].isFile()) {
            	files.add(children[i].getAbsolutePath());
            }
        }
        
        return files;
    }
    
    /**
     * Get recursively the files of a directory
     * 
     * @param files
     *            the list of files
     * @return the dataset size
     */
    private long getBytes(List<String> files) {
        if (files == null) throw new IllegalArgumentException(""+files);
        long size = 0;
        for (String file : files) {
        	size += (new File(file)).length();
        }
        
        return size;
    }
    
	private void download() {
		System.out.println("Download serverURL: " + serverURL);
		TestDownloadListener tl = new TestDownloadListener(lock, this, enableChecksum);
		TestFileDownloadImplementation fdi = new TestFileDownloadImplementation(serverURL, 
				tl, "", tagMap, new TestDownloadApplet(maxConnections, socketBufferSize, allowChunks, appletChunkSize), user, password);
		
		List<String> files = fdi.getFiles(controlNumber, 0);
		tl.setTotalFiles(files.size());
		tl.setTotalBytes(fdi.getSize());
		datasetSize = tl.getTotalBytes();
		fdi.setEnableChecksum(enableChecksum);
		long start = System.currentTimeMillis();
		fdi.downloadFiles(outputDir, "all");
		synchronized (lock) {
			while (!ready) {
				try {
					lock.wait();
				} catch (InterruptedException e) {
					// TODO Auto-generated catch block
					e.printStackTrace();
				}
			}
		}
		
		elapsed = System.currentTimeMillis() - start;
	}

	public void setReady(boolean ready) {
		this.ready = ready;
	}

	public boolean isReady() {
		return ready;
	}
	
	public static void testJSON() {
		String str = "[{\"bytes\":3751874,\"name\":\"All image studies\"}\n," +
				"{\"bytes\":null,\"name\":\"configuration tags\"}\n," +
				"{\"bytes\":null,\"name\":\"New image studies\"}\n," +
				"{\"bytes\":null,\"name\":\"OCT brief tags\"}\n," +
				"{\"bytes\":null,\"name\":\"OCT tags\"}\n," +
				"{\"bytes\":null,\"name\":\"Previous image studies\"}\n," +
				"{\"bytes\":null,\"name\":\"study tags\"}\n," +
				"{\"bytes\":null,\"name\":\"tagfiler configuration\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_# 0-16\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_# 0-9\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_date\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Diabetic Retinopathy Level\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_DRU Area\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_DRU Grid Type\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_float8\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_GA/Ex DA Lesions\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Inc Pigment\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Inc/RPE Lesions\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_int8\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Max DRU Size\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Max DRU Type\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Modality\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_no/yes\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_no/yes/CG\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Other Lesions\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Other Lesions +PT\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_role\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_rolepat\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_RPE Depigment\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_Study Name\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_tagname\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_text\"}\n," +
				"{\"bytes\":null,\"name\":\"_type_def_timestamptz\"}\n]";
		
		JSONArray array = null;
		try {
			array = new JSONArray(str);
		} catch (JSONException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		int length = array.length();
		System.out.println("length: " + length);
		for (int i=0; i<length; i++) {
			try {
				JSONObject obj = array.getJSONObject(i);
				if (obj.isNull("bytes")) {
					System.out.println("bytes null");
				} else {
					long bytes = obj.getLong("bytes");
					System.out.println("bytes: " + bytes);
				}
				String name = obj.getString("name");
				System.out.println("name: " + name);
			} catch (JSONException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		}
		
		System.exit(0);
	}
    
		public static String join(Set<String> strings, String delimiter){
		  if(strings==null || delimiter == null) {
		    return null;
		  }
		 
		  StringBuffer buf = new StringBuffer();
		  boolean first = true;
		  
		  for (String value : strings) {
			  if (first) {
				  first = false;
			  } else {
			      buf.append(delimiter);
			  }
			  buf.append(value);
		  }
		 
		  return buf.toString();
		}
		
		public static void testDigest() {
			try {
				String filename = "/home/serban/5G/50.6.gigafile";
				try {
					System.out.println("Starting...");
					long t0 = System.currentTimeMillis();
					InputStream fis =  new FileInputStream(filename);
					MessageDigest md = MessageDigest.getInstance("SHA-256");
					byte[] buffer = new byte[4194304];
					int numRead = 0;
					try {
						numRead = fis.read(buffer);
					} catch (IOException e1) {
						// TODO Auto-generated catch block
						e1.printStackTrace();
					}
					while (numRead != -1) {
						try {
							md.update(buffer, 0, numRead);
							numRead = fis.read(buffer);
						} catch (IOException e) {
							// TODO Auto-generated catch block
							e.printStackTrace();
						}
					}
					try {
						byte data[] = md.digest();
						System.out.println((System.currentTimeMillis() - t0) + " ms.");
						String res = getChecksum(data);
						System.out.println(res);
						fis.close();
					} catch (IOException e) {
						// TODO Auto-generated catch block
						e.printStackTrace();
					}
				} catch (FileNotFoundException e) {
					// TODO Auto-generated catch block
					e.printStackTrace();
				}
			} catch (NoSuchAlgorithmException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}

			System.exit(0);
			
		}

		   public static String getChecksum(byte[] cksum) {
			     String result = "";
			     for (int i=0; i < cksum.length; i++) {
			       result +=
			          Integer.toString( ( cksum[i] & 0xff ) + 0x100, 16).substring( 1 );
			      }
			     return result;
			   }
}
