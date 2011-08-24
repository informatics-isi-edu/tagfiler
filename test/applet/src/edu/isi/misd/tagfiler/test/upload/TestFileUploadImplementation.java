package edu.isi.misd.tagfiler.test.upload;

import edu.isi.misd.tagfiler.TagFilerUploadApplet;
import edu.isi.misd.tagfiler.client.ClientURLResponse;
import edu.isi.misd.tagfiler.ui.CustomTagMap;
import edu.isi.misd.tagfiler.ui.FileListener;
import edu.isi.misd.tagfiler.upload.FileUploadImplementation;

public class TestFileUploadImplementation extends FileUploadImplementation {

	public TestFileUploadImplementation(String url, FileListener l,
			String c, CustomTagMap tagMap, TagFilerUploadApplet a, String user, String password) {
		super(url, l, tagMap, c, a);
		// TODO Auto-generated constructor stub
		
		int index = url.lastIndexOf("/");
		String loginURL = url.substring(0, index) + "/webauthn/login";
		ClientURLResponse response = client.login(loginURL, user, password);
		int status = response.getStatus();
		if (status == 200 || status == 303) {
			cookie = client.updateSessionCookie(a, null);
		}
		if (cookie == null) {
			System.out.println("Login failure" );
			System.exit(1);
		}
	}

}
