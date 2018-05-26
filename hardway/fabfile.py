import os
import binascii
from fabric.api import local, lcd
from mako.template import Template

def init_env(region='us-west1', zone='us-west1-c', os='osx'):
    local('gcloud config set compute/region us-west1')
    local('gcloud config set compute/zone us-west1-c')

def cfssl(os='osx'):
    if os == 'osx':
        local('brew install cfssl')

def kubectl(os='osx'):
    if os == 'osx':
        local('curl -o kubectl https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/darwin/amd64/kubectl')
        local ('chmod +x kubectl')
        local('mv kubectl /usr/local/bin/')

# create vpc, subnet and firewall rules
def networking(name='kubernetes-the-hard-way', cidr='10.240.0.0/24', subnet_name='kubernetes'):
    local('gcloud compute networks create {0} --subnet-mode custom'.format(name))
    local('gcloud compute networks subnets create {0} --network {1} --range {2}'.format(subnet_name, name, cidr))


def firewall_rules(name='kubernetes-the-hard-way'):
    # internal
    local('gcloud compute firewall-rules create kubernetes-internal-firewall --allow tcp,udp,icmp --network {0} --source-ranges 10.240.0.0/24,10.200.0.0/16'.format(name))
    # external
    local('gcloud compute firewall-rules create kubernetes-external-firewall --allow tcp:22,tcp:6443,icmp --network {0} --source-ranges 0.0.0.0/0'.format(name))
    local('gcloud compute firewall-rules list --filter="network:{0}"'.format(name))

def public_ip(name='kubernetes-the-hard-way', region='us-west1'):
    local('gcloud compute addresses create {0} --region {1}'.format(name, region))

def create_controllers():
    for i in range(0, 3):
        local('gcloud compute instances create controller-{0} --async --boot-disk-size 200GB \
    --can-ip-forward \
    --image-family ubuntu-1804-lts \
    --image-project ubuntu-os-cloud \
    --machine-type n1-standard-1 \
    --private-network-ip 10.240.0.1{0} \
    --scopes compute-rw,storage-ro,service-management,service-control,logging-write,monitoring \
    --subnet kubernetes \
    --tags kubernetes-the-hard-way,controller'.format(i))

def create_workers():
    for i in range(0,3):
        local('gcloud compute instances create worker-{0} \
    --async \
    --boot-disk-size 200GB \
    --can-ip-forward \
    --image-family ubuntu-1804-lts \
    --image-project ubuntu-os-cloud \
    --machine-type n1-standard-1 \
    --metadata pod-cidr=10.200.{0}.0/24 \
    --private-network-ip 10.240.0.2{0} \
    --scopes compute-rw,storage-ro,service-management,service-control,logging-write,monitoring \
    --subnet kubernetes \
    --tags kubernetes-the-hard-way,worker'.format(i))

def generate_ca():
    with lcd('ca'):
        local('cfssl gencert -initca ca-csr.json | cfssljson -bare ca')

def generate_admin_cert():
    with lcd('admin'):
        local('cfssl gencert -ca=../ca/ca.pem -ca-key=../ca/ca-key.pem -config=../ca/ca-config.json -profile=kubernetes admin-csr.json | cfssljson -bare admin')

def generate_kubelet_cert():
    with lcd('kubelet'):
        for i in range(0,3):
            ex_output = local("gcloud compute instances describe worker-{0} --format 'value(networkInterfaces[0].accessConfigs[0].natIP)'".format(i), capture=True)
            in_output = local("gcloud compute instances describe worker-{0} --format 'value(networkInterfaces[0].networkIP)'".format(i), capture=True)
            print (ex_output, in_output)
            local('cfssl gencert -ca=../ca/ca.pem -ca-key=../ca/ca-key.pem -config=../ca/ca-config.json \
  -hostname=worker-{0},{1},{2} \
  -profile=kubernetes \
  worker-{0}-csr.json | cfssljson -bare worker-{0}'.format(i, ex_output, in_output))

def generate_control_manager_cert():
    with lcd('control_manager'):
        local('cfssl gencert \
  -ca=../ca/ca.pem \
  -ca-key=../ca/ca-key.pem \
  -config=../ca/ca-config.json \
  -profile=kubernetes \
  kube-controller-manager-csr.json | cfssljson -bare kube-controller-manager')


def generate_kube_proxy_cert():
    with lcd('kube_proxy'):
        local('cfssl gencert \
  -ca=../ca/ca.pem \
  -ca-key=../ca/ca-key.pem \
  -config=../ca/ca-config.json \
  -profile=kubernetes \
  kube-proxy-csr.json | cfssljson -bare kube-proxy')


def generate_scheduler_cert():
    with lcd('scheduler'):
        local('cfssl gencert \
  -ca=../ca/ca.pem \
  -ca-key=../ca/ca-key.pem \
  -config=../ca/ca-config.json \
  -profile=kubernetes \
  kube-scheduler-csr.json | cfssljson -bare kube-scheduler')

def generate_api_server_cert():
    with lcd('api_server'):
        public_ip = local("""gcloud compute addresses describe kubernetes-the-hard-way """
                    """--region us-west1 --format 'value(address)'""", capture=True)
        local("""cfssl gencert -ca=../ca/ca.pem -ca-key=../ca/ca-key.pem -config=../ca/ca-config.json """
            """-hostname=10.32.0.1,10.240.0.10,10.240.0.11,10.240.0.12,{0},127.0.0.1,kubernetes.default """
            """-profile=kubernetes kubernetes-csr.json | cfssljson -bare kubernetes""".format(public_ip))

def generate_service_account_cert():
    with lcd('sa'):
        local("""cfssl gencert -ca=../ca/ca.pem -ca-key=../ca/ca-key.pem -config=../ca/ca-config.json """
            """-profile=kubernetes service-account-csr.json | cfssljson -bare service-account""")

def copy_certs():
    for i in range(0, 3):
        local('gcloud compute scp ca/ca.pem kubelet/worker-{0}-key.pem kubelet/worker-{0}.pem worker-{0}:~/'.format(i))
        local('gcloud compute scp ca/ca.pem ca/ca-key.pem api_server/kubernetes-key.pem api_server/kubernetes.pem sa/service-account-key.pem sa/service-account.pem controller-{0}:~/'.format(i))

def create_kubelet_config():
    public_ip = local("""gcloud compute addresses describe kubernetes-the-hard-way """
                      """--region us-west1 --format 'value(address)'""", capture=True)
    for i in range(0, 3):
        with lcd('kubelet'):
            local("""kubectl config set-cluster kubernetes-the-hard-way --certificate-authority=../ca/ca.pem --embed-certs=true """
            """--server=https://{0}:6443 --kubeconfig=worker-{1}.kubeconfig""".format(public_ip, i))
            local("""kubectl config set-credentials system:node:worker-{0} --client-certificate=worker-{0}.pem --client-key=worker-{0}-key.pem """
            """--embed-certs=true --kubeconfig=worker-{0}.kubeconfig""".format(i))
            local("""kubectl config set-context default --cluster=kubernetes-the-hard-way --user=system:node:worker-{0} """
             """--kubeconfig=worker-{0}.kubeconfig""".format(i))
            local("""kubectl config use-context default --kubeconfig=worker-{0}.kubeconfig""".format(i))

def create_kube_proxy_config():
    public_ip = local("""gcloud compute addresses describe kubernetes-the-hard-way """
                      """--region us-west1 --format 'value(address)'""", capture=True)
    create_config(name='kube-proxy', dir_name='kube_proxy', server_ip=public_ip)

def create_controller_manager_config():
    public_ip = local("""gcloud compute addresses describe kubernetes-the-hard-way """
                      """--region us-west1 --format 'value(address)'""", capture=True)
    create_config(name='kube-controller-manager',
                  dir_name='control_manager', server_ip=public_ip)

def create_scheduler_config():
    public_ip = local("""gcloud compute addresses describe kubernetes-the-hard-way """
                      """--region us-west1 --format 'value(address)'""", capture=True)
    create_config(name='kube-scheduler',
                  dir_name='scheduler', server_ip=public_ip)

def create_admin_config():
    server_ip = "127.0.0.1"
    create_config(name='admin', dir_name='admin', server_ip=server_ip)

def copy_config():
    for i in range(0, 3):
        local('gcloud compute scp kubelet/worker-{0}.kubeconfig kube_proxy/kube-proxy.kubeconfig worker-{0}:~/'.format(i))
        local('gcloud compute scp admin/admin.kubeconfig control_manager/kube-controller-manager.kubeconfig scheduler/kube-scheduler.kubeconfig controller-{0}:~/'.format(i))

def create_config(name, dir_name, server_ip):
    with lcd(dir_name):
        local("""kubectl config set-cluster kubernetes-the-hard-way --certificate-authority=../ca/ca.pem --embed-certs=true """
            """--server=https://{0}:6443 --kubeconfig={1}.kubeconfig""".format(server_ip, name))
        local("""kubectl config set-credentials system:node:{0} --client-certificate={0}.pem --client-key={0}-key.pem """
            """--embed-certs=true --kubeconfig={0}.kubeconfig""".format(name))
        local("""kubectl config set-context default --cluster=kubernetes-the-hard-way --user=system:node:{0} """
            """--kubeconfig={0}.kubeconfig""".format(name))
        local("""kubectl config use-context default --kubeconfig={0}.kubeconfig""".format(name))

def setup_encryption():
    mytemplate = Template(
        filename='templates/encryption-config.mako',
        module_directory='/tmp/mako_modules')
    key = str(binascii.b2a_base64(os.urandom(32)), 'utf-8')
    with open('encryption/encryption-config.yaml', 'w') as f:
        f.write(mytemplate.render(encryption_key=key))
    for i in range(0, 3):
        local('gcloud compute scp encryption/encryption-config.yaml controller-{0}:~/'.format(i))

# setup 07
def run_command(host, command):
    """
    Utility function to run commads in remote host
    """
    local("gcloud compute ssh {0} --command '{1}'".format(host, command))

def setup_etcd():
    for i in range(0, 3):
        internal_ip = local(
            "gcloud compute instances describe controller-{0} --format 'value(networkInterfaces[0].networkIP)'".format(i), capture=True)
        mytemplate = Template(
            filename='etcd/etcd.service.mako',
            module_directory='/tmp/mako_modules')
        with open('etcd/etcd.service.{0}'.format(i), 'w') as f:
            f.write(mytemplate.render(internal_ip=internal_ip, name='controller-{0}'.format(i)))
        host_name = "controller-{0}".format(i)
        local(
            'gcloud compute scp etcd/etcd.service.{0} controller-{0}:~/etcd.service'.format(i))
        local(
            "gcloud compute ssh controller-{0} --command 'sudo cp ~/etcd.service /etc/systemd/system/etcd.service'".format(i))
        run_command(
            host=host_name, 
            command='wget -q --show-progress --https-only --timestamping "https://github.com/coreos/etcd/releases/download/v3.3.5/etcd-v3.3.5-linux-amd64.tar.gz"')
        run_command(
            host=host_name, 
            command="tar -xvf etcd-v3.3.5-linux-amd64.tar.gz && sudo mv etcd-v3.3.5-linux-amd64/etcd* /usr/local/bin/")
        run_command(
            host=host_name,
            command="sudo mkdir -p /etc/etcd /var/lib/etcd")
        run_command(
            host=host_name,
            command="sudo cp ca.pem kubernetes-key.pem kubernetes.pem /etc/etcd/")
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable etcd && sudo systemctl start etcd")

def verify_etcd():
    run_command(
        host="controller-0",
        command="sudo ETCDCTL_API=3 etcdctl member list --endpoints=https://127.0.0.1:2379 --cacert=/etc/etcd/ca.pem \
  --cert=/etc/etcd/kubernetes.pem --key=/etc/etcd/kubernetes-key.pem")

def setup_controller():
    for i in range(0, 3):
        host_name = "controller-{0}".format(i)
        run_command(
            host=host_name,
            command="sudo mkdir -p /etc/kubernetes/config")
        run_command(
            host=host_name,
            command='wget -q --show-progress --https-only --timestamping \
  "https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kube-apiserver" \
  "https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kube-controller-manager" \
  "https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kube-scheduler" \
  "https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kubectl"')
        # run_command(
        #     host=host_name,
        #     command='chmod +x kube-apiserver kube-controller-manager kube-scheduler kubectl && sudo cp kube-apiserver kube-controller-manager kube-scheduler kubectl /usr/local/bin/'
        # )
        run_command(
            host=host_name,
            command='sudo mkdir -p /var/lib/kubernetes/')
        run_command(
            host=host_name,
            command='sudo cp ca.pem ca-key.pem kubernetes-key.pem kubernetes.pem service-account-key.pem service-account.pem encryption-config.yaml /var/lib/kubernetes/')

def copy_file(host, src, destination):
    """
    Utility function to copy files to remote instance
    """
    tmp_file = str(binascii.b2a_hex(os.urandom(10)), 'utf-8')
    local(
        'gcloud compute scp {0} {1}:~/{2}'.format(src, host, tmp_file))
    local(
        "gcloud compute ssh {0} --command 'sudo cp ~/{1} {2}'".format(host, tmp_file, destination))
    local(
        "gcloud compute ssh {0} --command 'sudo rm ~/{1}'".format(host, tmp_file))

def setup_api_server():
    for i in range(0, 3):
        internal_ip = local(
            "gcloud compute instances describe controller-{0} --format 'value(networkInterfaces[0].networkIP)'".format(i), capture=True)
        host_name = "controller-{0}".format(i)
        mytemplate = Template(
            filename='templates/kube-apiserver.service.mako',
            module_directory='/tmp/mako_modules')
        with open('api_server/kube-apiserver.service.{0}'.format(i), 'w') as f:
            f.write(mytemplate.render(internal_ip=internal_ip))
        copy_file(
            host=host_name, 
            src='api_server/kube-apiserver.service.{0}'.format(i), 
            destination='/etc/systemd/system/kube-apiserver.service')
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable kube-apiserver && sudo systemctl start kube-apiserver")

def setup_controller_manager():
    for i in range(0, 3):
        host_name = "controller-{0}".format(i)
        run_command(
            host=host_name,
            command='sudo cp kube-controller-manager.kubeconfig /var/lib/kubernetes/')
        copy_file(
            host=host_name,
            src='control_manager/kube-controller-manager.service',
            destination='/etc/systemd/system/kube-controller-manager.service')
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable kube-controller-manager && sudo systemctl start kube-controller-manager")
                                      
def setup_scheduler():
    for i in range(0, 3):
        host_name = "controller-{0}".format(i)
        run_command(
            host=host_name,
            command='sudo cp kube-scheduler.kubeconfig /var/lib/kubernetes/')
        copy_file(
            host=host_name,
            src='scheduler/kube-scheduler.yaml',
            destination='/etc/kubernetes/config/kube-scheduler.yaml')
        copy_file(
            host=host_name,
            src='scheduler/kube-scheduler.service',
            destination='/etc/systemd/system/kube-scheduler.service')
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable kube-scheduler && sudo systemctl start kube-scheduler")

def setup_nginx():
     for i in range(0, 3):
        host_name = "controller-{0}".format(i)
        run_command(
            host=host_name,
            command='sudo apt-get install -y nginx')
        copy_file(
            host=host_name,
            src='nginx/kubernetes.default.svc.cluster.local',
            destination='/etc/nginx/sites-available/kubernetes.default.svc.cluster.local')
        run_command(
            host=host_name,
            command='sudo rm -f /etc/nginx/sites-enabled/kubernetes.default.svc.cluster.local')
        run_command(
             host=host_name,
             command='sudo ln -s /etc/nginx/sites-available/kubernetes.default.svc.cluster.local /etc/nginx/sites-enabled/')
        run_command(
            host=host_name,
            command='sudo systemctl restart nginx')
        run_command(
            host=host_name,
            command='systemctl enable nginx')
        
def setup_rbac():
    host_name = "controller-0"
    copy_file(
        host=host_name,
        src='admin/rbac-authorization.yaml',
        destination='/etc/rbac-authorization.yaml')
    run_command(
        host=host_name,
        command='kubectl apply --kubeconfig admin.kubeconfig -f /etc/rbac-authorization.yaml')

def setup_lb():
    public_ip = local("""gcloud compute addresses describe kubernetes-the-hard-way """
                      """--region us-west1 --format 'value(address)'""", capture=True)
    local("""gcloud compute http-health-checks create kubernetes --description \"Kubernetes Health Check\" """
        """--host \"kubernetes.default.svc.cluster.local\" --request-path \"/healthz\" """)
    local("""gcloud compute firewall-rules create kubernetes-the-hard-way-allow-health-check """
        """--network kubernetes-the-hard-way --source-ranges 209.85.152.0/22,209.85.204.0/22,35.191.0.0/16 --allow tcp""")
    local("""gcloud compute target-pools create kubernetes-target-pool --http-health-check kubernetes""")
    local("""gcloud compute target-pools add-instances kubernetes-target-pool --instances controller-0,controller-1,controller-2""")
    local("""gcloud compute forwarding-rules create kubernetes-forwarding-rule --address {0} --ports 6443 """
        """--region $(gcloud config get-value compute/region) --target-pool kubernetes-target-pool""".format(public_ip))

### worker node setup ###
def setup_worker():
    for i in range(0, 3):
        host_name = "worker-{0}".format(i)
        run_command(
            host=host_name,
            command='sudo apt-get update && sudo apt-get -y install socat conntrack ipset')
        run_command(
            host=host_name,
            command="""wget -q --show-progress --https-only --timestamping """
                """https://github.com/kubernetes-incubator/cri-tools/releases/download/v1.0.0-beta.0/crictl-v1.0.0-beta.0-linux-amd64.tar.gz """
                """https://storage.googleapis.com/kubernetes-the-hard-way/runsc """
                """https://github.com/opencontainers/runc/releases/download/v1.0.0-rc5/runc.amd64 """
                """https://github.com/containernetworking/plugins/releases/download/v0.6.0/cni-plugins-amd64-v0.6.0.tgz """
                """https://github.com/containerd/containerd/releases/download/v1.1.0/containerd-1.1.0.linux-amd64.tar.gz """
                """https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kubectl """
                """https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kube-proxy """
                """https://storage.googleapis.com/kubernetes-release/release/v1.10.2/bin/linux/amd64/kubelet """)
        run_command(
            host=host_name,
            command="""sudo mkdir -p /etc/cni/net.d /opt/cni/bin /var/lib/kubelet """
                """/var/lib/kube-proxy /var/lib/kubernetes /var/run/kubernetes"""
        )
        run_command(
            host=host_name,
            command='chmod +x kubectl kube-proxy kubelet runc.amd64 runsc'
        )
        run_command(
            host=host_name,
            command='sudo cp runc.amd64 runc'
        )
        run_command(
            host=host_name,
            command=' sudo cp kubectl kube-proxy kubelet runc runsc /usr/local/bin/'
        )
        run_command(
            host=host_name,
            command='sudo tar -xvf crictl-v1.0.0-beta.0-linux-amd64.tar.gz -C /usr/local/bin/'
        )
        run_command(
            host=host_name,
            command='sudo tar -xvf cni-plugins-amd64-v0.6.0.tgz -C /opt/cni/bin/'
        )
        run_command(
            host=host_name,
            command='sudo tar -xvf containerd-1.1.0.linux-amd64.tar.gz -C /'
        )

def setup_cni():
    for i in range(0, 3):
        host_name = "worker-{0}".format(i)
        pod_cidr = '10.200.{0}.0/24'.format(i)
        mytemplate = Template(
            filename='templates/10-bridge.conf.mako',
            module_directory='/tmp/mako_modules')
        with open('cni/10-bridge.conf.{0}'.format(i), 'w') as f:
            f.write(mytemplate.render(pod_cidr=pod_cidr))
        copy_file(
            host=host_name,
            src='cni/10-bridge.conf.{0}'.format(i),
            destination='/etc/cni/net.d/10-bridge.conf'
        )
        copy_file(
            host=host_name,
            src='cni/99-loopback.conf',
            destination='/etc/cni/net.d/99-loopback.conf'
        )

def setup_containerd():
    for i in range(0, 3):
        host_name = "worker-{0}".format(i)
        run_command(
            host=host_name,
            command='sudo mkdir -p /etc/containerd/'
        )
        copy_file(
            host=host_name,
            src='containerd/config.toml',
            destination='/etc/containerd/config.toml'
        )
        copy_file(
            host=host_name,
            src='containerd/containerd.service',
            destination='/etc/systemd/system/containerd.service'
        )
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable containerd && sudo systemctl start containerd")

def setup_kubelet():
    for i in range(0, 3):
        host_name = "worker-{0}".format(i)
        pod_cidr = '10.200.{0}.0/24'.format(i)
        """
        sudo mv ${HOSTNAME}-key.pem ${HOSTNAME}.pem /var/lib/kubelet/
        sudo mv ${HOSTNAME}.kubeconfig /var/lib/kubelet/kubeconfig
        sudo mv ca.pem /var/lib/kubernetes/
        """
        run_command(
            host=host_name,
            command='sudo cp {0}-key.pem {0}.pem /var/lib/kubelet/'.format(host_name)
        )
        run_command(
            host=host_name,
            command='sudo cp {0}.kubeconfig /var/lib/kubelet/kubeconfig'.format(host_name)
        )
        run_command(
            host=host_name,
            command='sudo cp ca.pem /var/lib/kubernetes/'
        )
        mytemplate = Template(
            filename='templates/kubelet-config.yaml.mako',
            module_directory='/tmp/mako_modules')
        with open('kubelet/kubelet-config.yaml.{0}'.format(i), 'w') as f:
            f.write(mytemplate.render(pod_cidr=pod_cidr, host_name=host_name))
        copy_file(
            host=host_name,
            src='kubelet/kubelet-config.yaml.{0}'.format(i),
            destination='/var/lib/kubelet/kubelet-config.yaml'
        )
        copy_file(
            host=host_name,
            src='kubelet/kubelet.service',
            destination='/etc/systemd/system/kubelet.service'
        )
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable kubelet && sudo systemctl start kubelet")

def setup_kube_proxy():
    for i in range(0, 3):
        host_name = "worker-{0}".format(i)
        run_command(
            host=host_name,
            command='sudo cp kube-proxy.kubeconfig /var/lib/kube-proxy/kubeconfig'
        )
        copy_file(
            host=host_name,
            src='kube_proxy/kube-proxy-config.yaml',
            destination='/var/lib/kube-proxy/kube-proxy-config.yaml'
        )
        copy_file(
            host=host_name,
            src='kube_proxy/kube-proxy.service',
            destination='/etc/systemd/system/kube-proxy.service'
        )
        run_command(
            host=host_name,
            command="sudo systemctl daemon-reload && sudo systemctl enable kube-proxy && sudo systemctl start kube-proxy")
##### defining steps for the process ###########################################

def step_01():
    init_env()
    cfssl()
    kubectl()

def step_02():
    # setting up networking and firewall rules
    networking()
    firewall_rules()
    public_ip()
    create_controllers()
    create_workers()

def step_03():
    # generate client certificates and distribute them
    generate_ca()
    generate_admin_cert()
    generate_kubelet_cert()
    generate_kube_proxy_cert()
    generate_scheduler_cert()
    generate_api_server_cert()
    generate_control_manager_cert()
    generate_service_account_cert()
    copy_certs()

def step_04():
    # generate kubeconfig and distributes them
    create_kube_proxy_config()
    create_kubelet_config()
    create_controller_manager_config()
    create_scheduler_config()
    create_admin_config()
    copy_config()

def step_05():
    setup_encryption()

def step_06():
    setup_etcd()
    verify_etcd()

def step_07():
    setup_controller()
    setup_api_server()
    setup_controller_manager()
    setup_scheduler()
    setup_nginx()
    setup_rbac()
    setup_lb()

def step_08():
    setup_worker()
    setup_cni()
    setup_containerd()
    setup_kubelet()
    setup_kube_proxy()