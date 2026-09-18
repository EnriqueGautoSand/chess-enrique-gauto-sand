@echo off
echo Habilitando el puerto 5000 en el Firewall de Windows para Flask...
netsh advfirewall firewall add rule name="Flask Chess TCP 5000" dir=in action=allow protocol=TCP localport=5000
echo.
echo =======================================================
echo   Puerto 5000 habilitado con exito en el Firewall!
echo   Ya puedes acceder desde celulares y otras PCs.
echo =======================================================
echo.
pause
