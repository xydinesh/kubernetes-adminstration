kind: KubeletConfiguration
apiVersion: kubelet.config.k8s.io/v1beta1
authentication:
  anonymous:
    enabled: false
  webhook:
    enabled: true
  x509:
    clientCAFile: "/var/lib/kubernetes/ca.pem"
authorization:
  mode: Webhook
clusterDomain: "cluster.local"
clusterDNS:
  - "10.32.0.10"
podCIDR: "${pod_cidr}"
runtimeRequestTimeout: "15m"
tlsCertFile: "/var/lib/kubelet/${host_name}.pem"
tlsPrivateKeyFile: "/var/lib/kubelet/${host_name}-key.pem"
