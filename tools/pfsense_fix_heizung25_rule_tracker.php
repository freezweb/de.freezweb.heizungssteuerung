global $config;

$changed = false;
$new_tracker = '1781625201';

if (is_array($config['filter']['rule'])) {
    foreach ($config['filter']['rule'] as &$rule) {
        if (($rule['descr'] ?? '') == 'HEIZUNG_25 initial outbound allow' ||
            ($rule['tracker'] ?? '') == 'codex-heizung-25-initial-allow') {
            $rule['tracker'] = $new_tracker;
            $changed = true;
            echo "fixed HEIZUNG_25 rule tracker\n";
        }
    }
    unset($rule);
}

if ($changed) {
    write_config('Codex: fix HEIZUNG_25 firewall rule tracker');
    if (function_exists('filter_configure')) {
        filter_configure();
    }
    echo "filter reloaded\n";
} else {
    echo "no matching rule found\n";
}
