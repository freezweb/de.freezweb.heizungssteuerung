global $config;

$iface_descr = 'HEIZUNG_25';
$static_maps = array(
    array(
        'mac' => 'c8:3e:a7:10:da:39',
        'ip' => '10.1.25.10',
        'hostname' => 'revpi-hauptsteuerung',
        'descr' => 'RevPi Hauptsteuerung'
    ),
    array(
        'mac' => 'c8:3e:a7:10:d9:fd',
        'ip' => '10.1.25.11',
        'hostname' => 'revpi-zweitsteuerung',
        'descr' => 'RevPi Zweitsteuerung'
    )
);
$changed = false;

$iface_key = null;
foreach ($config['interfaces'] as $key => $iface) {
    if (($iface['descr'] ?? '') === $iface_descr) {
        $iface_key = $key;
        break;
    }
}

if ($iface_key === null) {
    echo "interface $iface_descr not found\n";
    return;
}

if (!is_array($config['dhcpd'])) {
    $config['dhcpd'] = array();
}
if (!is_array($config['dhcpd'][$iface_key] ?? null)) {
    $config['dhcpd'][$iface_key] = array();
}
if (!is_array($config['dhcpd'][$iface_key]['staticmap'] ?? null)) {
    $config['dhcpd'][$iface_key]['staticmap'] = array();
}

foreach ($static_maps as $desired) {
    $found = false;
    foreach ($config['dhcpd'][$iface_key]['staticmap'] as &$map) {
        if (strtolower($map['mac'] ?? '') === $desired['mac']) {
            $found = true;
            if (($map['ipaddr'] ?? '') !== $desired['ip']) {
                $map['ipaddr'] = $desired['ip'];
                $changed = true;
            }
            if (($map['hostname'] ?? '') !== $desired['hostname']) {
                $map['hostname'] = $desired['hostname'];
                $changed = true;
            }
            if (($map['descr'] ?? '') !== $desired['descr']) {
                $map['descr'] = $desired['descr'];
                $changed = true;
            }
            break;
        }
    }
    unset($map);

    if (!$found) {
        $config['dhcpd'][$iface_key]['staticmap'][] = array(
            'mac' => $desired['mac'],
            'ipaddr' => $desired['ip'],
            'hostname' => $desired['hostname'],
            'descr' => $desired['descr']
        );
        $changed = true;
        echo "added static map {$desired['mac']} -> {$desired['ip']}\n";
    } else {
        echo "static map {$desired['mac']} exists\n";
    }
}

if ($changed) {
    write_config('Codex: add HEIZUNG_25 DHCP static map for RevPi Hauptsteuerung');
    if (function_exists('services_dhcpd_configure')) {
        services_dhcpd_configure();
    }
    echo "dhcp reloaded for $iface_descr ($iface_key)\n";
} else {
    echo "no changes\n";
}
