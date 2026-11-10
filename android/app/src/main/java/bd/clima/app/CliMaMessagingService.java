package bd.clima.app;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
public class CliMaMessagingService extends FirebaseMessagingService {
 @Override public void onNewToken(String token){getSharedPreferences("clima",MODE_PRIVATE).edit().putString("push_token",token).apply();}
 @Override public void onMessageReceived(RemoteMessage message){
  android.app.NotificationManager manager=getSystemService(android.app.NotificationManager.class);
  android.content.Intent intent=new android.content.Intent(this,MainActivity.class);
  android.app.PendingIntent pi=android.app.PendingIntent.getActivity(this,0,intent,android.app.PendingIntent.FLAG_IMMUTABLE|android.app.PendingIntent.FLAG_UPDATE_CURRENT);
  android.app.Notification notification=new android.app.Notification.Builder(this,"clima_updates").setContentTitle("CliMa").setContentText("You have a new update. Open CliMa to view it.").setSmallIcon(android.R.drawable.ic_dialog_info).setContentIntent(pi).setAutoCancel(true).build();
  try {manager.notify(1001,notification);} catch(SecurityException ignored){}
 }
}
