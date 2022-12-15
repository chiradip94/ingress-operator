from kubernetes import client, config, watch
import yaml

config.load_kube_config()
api_instance = client.CoreV1Api()

with open("./config/config.yaml", 'r') as stream:
    cofigigurations = yaml.safe_load(stream)

def get_svc_details(svc_object):
    svc_details = {}
    enable_anotation = cofigigurations["configure"]["annotation"]["enable"]
    port_anotation = cofigigurations["configure"]["annotation"]["port"]
    path_anotation = cofigigurations["configure"]["annotation"]["path"]
    path_type_anotation = cofigigurations["configure"]["annotation"]["path_type"]
    host_prefix_anotation = cofigigurations["configure"]["annotation"]["host_prefix"]
    domain_anotation = cofigigurations["configure"]["annotation"]["domain"]
    if svc_object.metadata.annotations != None and enable_anotation in svc_object.metadata.annotations:
        if svc_object.metadata.annotations[enable_anotation] == "true":
            svc_details["namespace"] = svc_object.metadata.namespace
            svc_details["name"] = svc_object.metadata.name
            svc_details["port"] = svc_object.metadata.annotations[port_anotation]
            svc_details["path"] = svc_object.metadata.annotations[path_anotation]
            svc_details["path_type"] = svc_object.metadata.annotations[path_type_anotation] \
                if path_type_anotation in svc_object.metadata.annotations else "Exact"

            host_prefix = svc_object.metadata.annotations[host_prefix_anotation] \
                if host_prefix_anotation in svc_object.metadata.annotations else cofigigurations["host_prefix"]
            domain = svc_object.metadata.annotations[domain_anotation] \
                if domain_anotation in svc_object.metadata.annotations else cofigigurations["domain"]

            svc_details["host"] = f"{host_prefix}.{domain}"
            svc_details["ingress_annotations"] = cofigigurations["ingress_annotations"]

    return svc_details

def create_ingress(namespace, svc_name, svc_port, host, path="/", path_type="Exact", annotations={}):
    networking_v1_api = client.NetworkingV1Api()
    body = client.V1Ingress(
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(name=svc_name, annotations=annotations),
        spec=client.V1IngressSpec(
            rules=[client.V1IngressRule(
                host=host,
                http=client.V1HTTPIngressRuleValue(
                    paths=[client.V1HTTPIngressPath(
                        path=path,
                        path_type=path_type,
                        backend=client.V1IngressBackend(
                            service=client.V1IngressServiceBackend(
                                port=client.V1ServiceBackendPort(
                                    number=int(svc_port),
                                ),
                                name=svc_name)
                            )
                    )]
                )
            )
            ]
        )
    )
    # Creation of the Deployment in specified namespace
    networking_v1_api.create_namespaced_ingress(
        namespace=namespace,
        body=body
    )

def event():
    w = watch.Watch()
    for event in w.stream(api_instance.list_service_for_all_namespaces, timeout_seconds=0) :
        print(f"{event['type']} - {event['object'].metadata.name}")

        if event['type'] == "ADDED":
            ingress_details = get_svc_details(event["object"])
            print (ingress_details)
            if ingress_details:
                create_ingress(ingress_details["namespace"], ingress_details["name"], ingress_details["port"], ingress_details["host"], ingress_details["path"], ingress_details["path_type"], ingress_details["ingress_annotations"])

event()