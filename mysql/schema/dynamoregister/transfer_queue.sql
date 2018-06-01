CREATE TABLE `transfer_queue` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `subscription_id` bigint(20) unsigned NOT NULL,
  `source` int(11) unsigned NOT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `transfer` (`subscription_id`),
  KEY `source` (`source`),
  KEY `batch` (`batch_id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1 COLLATE=latin1_general_cs;
