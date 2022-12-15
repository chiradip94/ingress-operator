from kubernetes import client, config, watch
import yaml

config.load_kube_config()
api_instance = client.CoreV1Api()
networking_v1_api = client.NetworkingV1Api()

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


def is_ingress_present(name, namespace):
    available = False
    response = networking_v1_api.list_namespaced_ingress(namespace=namespace)
    for ing in response.items:
        if name == ing.metadata.name:
            available = True
    return available


def create_ingress(namespace, svc_name, svc_port, host, path="/", path_type="Exact", annotations={}):
    if is_ingress_present(svc_name,namespace):
        print(f"Ingress {svc_name}.{namespace} is already present present.")
        return
    print(f"Processing service {svc_name}.{namespace}")
    body = client.V1Ingress(
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(name=svc_name, annotations=annotations),
        spec=client.V1IngressSpec(
            ingress_class_name=cofigigurations["ingress_class_name"],
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
    try:
        networking_v1_api.create_namespaced_ingress(
            namespace=namespace,
            body=body
        )
        print(f"Created ingress {svc_name}.{namespace}")
    except Exception as e:
        print(f"Failed to create ingress {svc_name}.{namespace}")
        print(e)


def delete_ingress(name, namespace):
    if is_ingress_present(name,namespace):
        try:
            networking_v1_api.delete_namespaced_ingress(name, namespace)
            print(f"Deleted ingress {name}.{namespace}")
        except Exception as e:
            print(f"Failed to delete ingress {name}.{namespace}")
            print(e)
    else:
        print(f"Ingress {name}.{namespace} not present.")


def event():
    w = watch.Watch()
    for event in w.stream(api_instance.list_service_for_all_namespaces, timeout_seconds=0) :
        print(f"Detected: {event['type']} - {event['object'].metadata.name}")

        if event['type'] == "ADDED":
            ingress_details = get_svc_details(event["object"])
            if ingress_details:
                create_ingress(ingress_details["namespace"], ingress_details["name"], ingress_details["port"], ingress_details["host"], ingress_details["path"], ingress_details["path_type"], ingress_details["ingress_annotations"])
        elif event['type'] == "DELETED":
            ingress_details = get_svc_details(event["object"])
            if ingress_details:
                delete_ingress(name=ingress_details["name"], namespace=ingress_details["namespace"])

event()