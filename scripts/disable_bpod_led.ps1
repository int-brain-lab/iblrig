$portstring = $args[0]

# open connection
$port = new-Object System.IO.Ports.SerialPort($portstring, 9600, 'None', 8, 'one')
$port.Open()

# handshake
$port.Write('6')
if ($port.ReadByte() -ne 53) {
    exit 1
}

# disable led
Start-Sleep -m 200
$port.Write(':')
$port.Write([byte[]] (0), 0, 1)
Start-Sleep -m 200

# close connection
$port.Close()
