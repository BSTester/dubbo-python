from nacos.client import NacosClient as NCObject
from nacos.client import logger, group_key, read_file_str, json, truncate, HTTPError, HTTPStatus, NacosException, save_file


class NacosClient(NCObject):
    def __init__(self, server_addresses, endpoint=None, namespace=None, ak=None, sk=None, username=None, password=None):
        super(NacosClient, self).__init__(server_addresses=server_addresses, endpoint=endpoint, namespace=namespace, ak=ak, sk=sk, username=username, password=password)

    def get_methods_from_service(self, service, clusters=None, namespace_id=None, group_name=None):
        instance = self.list_naming_instance(service_name=service, clusters=clusters, namespace_id=namespace_id, group_name=group_name, healthy_only=True)
        methods = []
        for host in instance.get('hosts') or []:
            method_values = host.get('metadata', {}).get('methods', '')
            for method in method_values.split(','):
                if method not in methods: methods.append(method)
        return methods

    def get_service_list(self, timeout=None, namespace_id=None, group_name=None, page_no=1, page_size=1000, consumers=False, providers=True):
        logger.info("[get-service-list] namespace:%s, timeout:%s, namespace_id:%s, group_name:%s, page_no:%s, page_size:%s" % (
            self.namespace, timeout, namespace_id, group_name, page_no, page_size))
        def filter_content(data, consumers=consumers, providers=providers):
            if not isinstance(data, dict):
                data = json.loads(data)
            data_list = []
            for item in data.get('doms') or []:
                if providers and item.startswith('providers'):
                    data_list.append(item)
                if consumers and item.startswith('consumers'):
                    data_list.append(item)
            return data_list
        cache_key = group_key(providers and 'providers' or '', consumers and 'consumers' or '', self.namespace)
        # get from failover
        content = read_file_str(self.failover_base, cache_key)
        if content is None:
            logger.debug("[get-service-list] failover service is not exist for %s, try to get from server" % cache_key)
        else:
            logger.debug("[get-service-list] get %s from failover directory, content is %s" % (cache_key, truncate(content)))
            return filter_content(content, consumers=consumers, providers=providers)

        # get from server
        def get_from_server(content={}, page_no=page_no, page_size=page_size):
            params = {
                "groupName": group_name or '',
                "namespaceId": namespace_id or '',
                "pageNo": page_no or 1,
                "pageSize": page_size or 1000
            }
            try:
                resp = self._do_sync_req("/nacos/v1/ns/service/list", None, params, None, timeout or self.default_timeout)
                page_content = resp.read().decode("UTF-8")
                page_content = json.loads(page_content)
                if not content: 
                    content = page_content
                else:
                    content['doms'] = (content.get('doms') or []) + (page_content.get('doms') or [])
                if page_content.get('count') > (page_size * page_no):
                    content = get_from_server(content=content, page_no=page_no+1, page_size=page_size)
            except HTTPError as e:
                if e.code == HTTPStatus.CONFLICT:
                    logger.error(
                        "[get-service-list] service being modified concurrently for namespace:%s" % self.namespace)
                elif e.code == HTTPStatus.FORBIDDEN:
                    logger.error("[get-service-list] no right for namespace:%s" % self.namespace)
                    raise NacosException("Insufficient privilege.")
                else:
                    logger.error("[get-service-list] error code [:%s] for namespace:%s" % (e.code, self.namespace))
                    if self.no_snapshot:
                        raise
            except Exception as e:
                logger.exception("[get-service-list] exception %s occur" % str(e))
                if self.no_snapshot:
                    raise
            finally:
                return content
        content = get_from_server(page_no=page_no, page_size=page_size)

        if self.no_snapshot:
            return filter_content(content, consumers=consumers, providers=providers)

        if content is not None:
            logger.info(
                "[get-service-list] content from server:%s, namespace:%s, try to save snapshot" % (
                    truncate(content), self.namespace))
            try:
                content = json.dumps(content) if isinstance(content, dict) else content
                save_file(self.snapshot_base, cache_key, content)
            except Exception as e:
                logger.exception("[get-service-list] save snapshot failed for %s, namespace:%s" % (
                    str(e), self.namespace))
            return filter_content(content, consumers=consumers, providers=providers)

        logger.error("[get-service-list] get config from server failed, try snapshot, namespace:%s" % self.namespace)
        content = read_file_str(self.snapshot_base, cache_key)
        if content is None:
            logger.warning("[get-service-list] snapshot is not exist for %s." % cache_key)
        else:
            logger.debug("[get-service-list] get %s from snapshot directory, content is %s" % (cache_key, truncate(content)))
            return filter_content(content, consumers=consumers, providers=providers)
