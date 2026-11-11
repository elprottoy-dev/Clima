package bd.clima.app;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
public class CliMaMessagingService extends FirebaseMessagingService {
 @Override public void onNewToken(String token){getSharedPreferences("clima",MODE_PRIVATE).edit().putString("push_token",token).apply();}
 @Override public void onMessageReceived(RemoteMessage message){
  android.app.NotificationManager manager=getSystemService(android.app.NotificationManager.class);
  manager.createNotificationChannel(new android.app.NotificationChannel("clima_updates","CliMa আপডেট",android.app.NotificationManager.IMPORTANCE_DEFAULT));
  android.content.Intent intent=new android.content.Intent(this,MainActivity.class);
  android.app.PendingIntent pi=android.app.PendingIntent.getActivity(this,0,intent,android.app.PendingIntent.FLAG_IMMUTABLE|android.app.PendingIntent.FLAG_UPDATE_CURRENT);
  android.app.Notification notification=new android.app.Notification.Builder(this,"clima_updates").setContentTitle("CliMa").setContentText("আপনার নতুন আপডেট আছে। দেখতে CliMa খুলুন।").setSmallIcon(android.R.drawable.ic_dialog_info).setContentIntent(pi).setAutoCancel(true).build();
  String noticeId=message.getData().get("notice_id");
  try {manager.notify(noticeId==null?1001:noticeId.hashCode(),notification);} catch(SecurityException ignored){}
 }
}
