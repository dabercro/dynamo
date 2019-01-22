from dynamo.source.siteinfo import SiteInfoSource
from dynamo.dataformat import Configuration, Site

import logging
LOG = logging.getLogger(__name__)

class StaticSiteInfoSource(SiteInfoSource):
    """
    Site information source fully specified by the static configuration.
    """

    def __init__(self, config):
        SiteInfoSource.__init__(self, config)
        
        self.config = Configuration(config.sites)

        LOG.info('-----------in constructor of SiteInfoSource-------')
        LOG.info(self.config)

#        config_path = os.getenv('DYNAMO_SERVER_CONFIG', '/etc/dynamo/fom_config.json')
#        self.fom_config = Configuration(config_path)
#        self.fom_conditions = []

#        for condition_text, module, conf in self.fom_config.rlfsm.transfer:
#            if condition_text is not None: # default
#                condition = Condition(condition_text, site_variables)
#                self.fom_conditions.append((condition, module, conf))



    def get_site(self, name, inventory): #override
        try:
            site_config = self.config[name]
        except KeyError:
            raise RuntimeError('Site %s not in configuration')

        storage_type = Site.storage_type_val(site_config.storage_type)
        backend = site_config.backend

        LOG.info('--------in get_site-------------')
        LOG.info(name)

        site_obj = Site(name, host = site_config.host, storage_type = storage_type, backend = backend)
        if name in inventory.sites:
            old_site_obj = inventory.sites[name]
            LOG.info('found ' + name)
            LOG.info.(old_site_obj.x509proxy)
            site_obj.x509proxy = old_site_obj.x509proxy

        #for cond, module, conf in self.fom_conditions:
        #    if cond.match(site_obj):
        #        site_obj.x509proxy = conf.x509proxy
        return site_obj

    def get_site_list(self, inventory): #override
        site_list = []

        for name in self.config.keys():
            site_list.append(self.get_site(name,inventory))

        return site_list

    def get_site_status(self, site_name): #override
        try:
            site_config = self.config[site_name]
        except KeyError:
            raise RuntimeError('Site %s not in configuration')

        return Site.status_val(site_config.status)

    def get_filename_mapping(self, site_name): #override
        try:
            site_config = self.config[site_name]
        except KeyError:
            raise RuntimeError('Site %s not in configuration')

        result = {}
        for protocol, mappings in site_config.filename_mapping.items():
            result[protocol] = []
            for lfnpat, pfnpat in mappings:
                result[protocol].append([(lfnpat, pfnpat)])

        return result
