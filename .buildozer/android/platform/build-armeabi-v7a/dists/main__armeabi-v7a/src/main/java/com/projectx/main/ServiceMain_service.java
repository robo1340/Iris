package com.projectx.main;

import android.content.Intent;
import android.content.Context;
import org.kivy.android.PythonService;


public class ServiceMain_service extends PythonService {
    

    @Override
    protected int getServiceId() {
        return 1;
    }

    static public void start(Context ctx, String pythonServiceArgument) {
        Intent intent = new Intent(ctx, ServiceMain_service.class);
        String argument = ctx.getFilesDir().getAbsolutePath() + "/app";
        intent.putExtra("androidPrivate", ctx.getFilesDir().getAbsolutePath());
        intent.putExtra("androidArgument", argument);
        intent.putExtra("serviceTitle", "NoBoB");
        intent.putExtra("serviceDescription", "Main_service");
        intent.putExtra("serviceEntrypoint", "./service/main.py");
        intent.putExtra("pythonName", "main_service");
        intent.putExtra("serviceStartAsForeground", "false");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument", pythonServiceArgument);
        ctx.startService(intent);
    }

    static public void stop(Context ctx) {
        Intent intent = new Intent(ctx, ServiceMain_service.class);
        ctx.stopService(intent);
    }
}