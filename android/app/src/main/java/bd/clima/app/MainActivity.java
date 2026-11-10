package bd.clima.app;
import android.app.Activity;
import android.os.Bundle;
import android.Manifest;
import android.content.pm.PackageManager;
import android.webkit.*;
import android.net.Uri;
import android.content.Intent;
import android.widget.TextView;
public class MainActivity extends Activity {
 // Replace with your deployed HTTPS server origin, without a trailing slash.
 private static final String APP_URL=BuildConfig.CLIMA_ORIGIN;
 private ValueCallback<Uri[]> fileCallback;
 private WebView web; private GeolocationPermissions.Callback pending; private String origin;
 @Override public void onCreate(Bundle state){super.onCreate(state);
  if(APP_URL.contains(".example")){TextView t=new TextView(this);t.setText("Configure APP_URL with your deployed HTTPS CliMa server before building the APK.");t.setPadding(30,60,30,30);setContentView(t);return;}
  web=new WebView(this);setContentView(web);web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setGeolocationEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
  web.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req){Uri u=req.getUrl();if("https".equals(u.getScheme())&&APP_URL.equals(u.getScheme()+"://"+u.getAuthority()))return false;if("https".equals(u.getScheme()))startActivity(new Intent(Intent.ACTION_VIEW,u));return true;}});
  web.setWebChromeClient(new WebChromeClient(){
   @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
    if(fileCallback!=null)fileCallback.onReceiveValue(null);
    fileCallback=callback;
    Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.addCategory(Intent.CATEGORY_OPENABLE);picker.setType("*/*");
    picker.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","image/jpeg","image/png"});
    try{startActivityForResult(picker,44);}catch(android.content.ActivityNotFoundException e){fileCallback.onReceiveValue(null);fileCallback=null;}
    return true;
   }
@Override public void onGeolocationPermissionsShowPrompt(String o,GeolocationPermissions.Callback cb){if(!o.equals(APP_URL)&&!o.equals(APP_URL+"/")){cb.invoke(o,false,false);return;}if(checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED){cb.invoke(o,true,false);return;}origin=o;pending=cb;requestPermissions(new String[]{Manifest.permission.ACCESS_COARSE_LOCATION,Manifest.permission.ACCESS_FINE_LOCATION},42);}});
  web.addJavascriptInterface(new Object(){@android.webkit.JavascriptInterface public void enableUpdates(){runOnUiThread(()->{
  if(android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},43);
  try { com.google.firebase.messaging.FirebaseMessaging.getInstance().getToken().addOnSuccessListener(value->{try{web.evaluateJavascript("window.dispatchEvent(new CustomEvent('clima-device-token',{detail:"+org.json.JSONObject.quote(value)+"}))",null);}catch(Exception ignored){}}); } catch(Exception ignored){}
 });}}, "CliMaDevice");
  if(android.os.Build.VERSION.SDK_INT>=26){android.app.NotificationManager nm=getSystemService(android.app.NotificationManager.class);nm.createNotificationChannel(new android.app.NotificationChannel("clima_updates","CliMa updates",android.app.NotificationManager.IMPORTANCE_DEFAULT));}
  web.loadUrl(APP_URL);
 }
 @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){super.onRequestPermissionsResult(code,permissions,results);if(code==42&&pending!=null){boolean granted=false;for(int r:results)if(r==PackageManager.PERMISSION_GRANTED)granted=true;pending.invoke(origin,granted,false);pending=null;}}
 @Override protected void onActivityResult(int request,int result,Intent data){
  super.onActivityResult(request,result,data);
  if(request==44&&fileCallback!=null){
   Uri value=result==RESULT_OK&&data!=null?data.getData():null;
   fileCallback.onReceiveValue(value!=null&&"content".equals(value.getScheme())?new Uri[]{value}:null);fileCallback=null;
  }
 }
 @Override protected void onDestroy(){if(fileCallback!=null){fileCallback.onReceiveValue(null);fileCallback=null;}super.onDestroy();}
 @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
}
