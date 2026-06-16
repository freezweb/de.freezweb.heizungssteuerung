global $config;

$changed = false;
$parent = 'ix0';
$tag = '25';
$ifname = $parent . '.' . $tag;
$descr = 'HEIZUNG_25';
$ip = '10.1.25.1';
$subnet = '24';

if (!is_array($config['vlans'])) {
    $config['vlans'] = array();
}
if (!is_array($config['vlans']['vlan'])) {
    $config['vlans']['vlan'] = array();
}

$vlan_exists = false;
foreach ($config['vlans']['vlan'] as &$vlan) {
    if (($vlan['if'] ?? '') == $parent && ($vlan['tag'] ?? '') == $tag) {
        $vlan_exists = true;
        if (($vlan['vlanif'] ?? '') != $ifname) {
            $vlan['vlanif'] = $ifname;
            $changed = true;
        }
        if (($vlan['descr'] ?? '') != 'heizung_25') {
            $vlan['descr'] = 'heizung_25';
            $changed = true;
        }
        break;
    }
}
unset($vlan);

if (!$vlan_exists) {
    $config['vlans']['vlan'][] = array(
        'if' => $parent,
        'tag' => $tag,
        'pcp' => '',
        'descr' => 'heizung_25',
        'vlanif' => $ifname
    );
    $changed = true;
    echo "added vlan $ifname\n";
} else {
    echo "vlan $ifname exists\n";
}

$iface_key = null;
foreach ($config['interfaces'] as $key => $iface) {
    if (($iface['if'] ?? '') == $ifname || strtoupper($iface['descr'] ?? '') == $descr) {
        $iface_key = $key;
        break;
    }
}

if ($iface_key === null) {
    $max = 0;
    foreach (array_keys($config['interfaces']) as $key) {
        if (preg_match('/^opt(\d+)$/', $key, $m)) {
            $max = max($max, intval($m[1]));
        }
    }
    $iface_key = 'opt' . ($max + 1);
    $config['interfaces'][$iface_key] = array();
    $changed = true;
    echo "added interface $iface_key\n";
} else {
    echo "interface $iface_key exists\n";
}

$config['interfaces'][$iface_key]['enable'] = '';
$config['interfaces'][$iface_key]['if'] = $ifname;
$config['interfaces'][$iface_key]['descr'] = $descr;
$config['interfaces'][$iface_key]['ipaddr'] = $ip;
$config['interfaces'][$iface_key]['subnet'] = $subnet;
$config['interfaces'][$iface_key]['ipaddrv6'] = 'none';
$config['interfaces'][$iface_key]['subnetv6'] = '';
$changed = true;

if (!is_array($config['dhcpd'])) {
    $config['dhcpd'] = array();
}
if (!is_array($config['dhcpd'][$iface_key] ?? null)) {
    $config['dhcpd'][$iface_key] = array();
}
$config['dhcpd'][$iface_key]['enable'] = '';
$config['dhcpd'][$iface_key]['range'] = array('from' => '10.1.25.100', 'to' => '10.1.25.199');
$config['dhcpd'][$iface_key]['defaultleasetime'] = '7200';
$config['dhcpd'][$iface_key]['maxleasetime'] = '86400';
$config['dhcpd'][$iface_key]['gateway'] = $ip;
$config['dhcpd'][$iface_key]['domain'] = 'home.arpa';
$changed = true;

$tracker = 'codex-heizung-25-initial-allow';
if (!is_array($config['filter'])) {
    $config['filter'] = array();
}
if (!is_array($config['filter']['rule'])) {
    $config['filter']['rule'] = array();
}

$rule_exists = false;
foreach ($config['filter']['rule'] as $rule) {
    if (($rule['tracker'] ?? '') == $tracker) {
        $rule_exists = true;
        break;
    }
}

if (!$rule_exists) {
    $config['filter']['rule'][] = array(
        'type' => 'pass',
        'interface' => $iface_key,
        'ipprotocol' => 'inet',
        'statetype' => 'keep state',
        'descr' => 'HEIZUNG_25 initial outbound allow',
        'tracker' => $tracker,
        'source' => array('network' => $iface_key),
        'destination' => array('any' => '')
    );
    $changed = true;
    echo "added firewall rule\n";
} else {
    echo "firewall rule exists\n";
}

if ($changed) {
    write_config('Codex: add HEIZUNG_25 VLAN/interface/DHCP/firewall');
    if (function_exists('interface_vlan_configure')) {
        interface_vlan_configure($ifname);
    }
    if (function_exists('interface_configure')) {
        interface_configure($iface_key, true);
    }
    if (function_exists('filter_configure')) {
        filter_configure();
    }
    if (function_exists('services_dhcpd_configure')) {
        services_dhcpd_configure();
    }
    echo "configured $descr on $ifname as $ip/$subnet ($iface_key)\n";
} else {
    echo "no changes\n";
}
