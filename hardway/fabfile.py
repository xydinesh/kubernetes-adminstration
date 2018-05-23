from fabric.api import local, lcd

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
    from mako.template import Template
    import os
    import binascii
    mytemplate = Template(
        filename='encryption/encryption-config.mako',
        module_directory='/tmp/mako_modules')
    key = str(binascii.b2a_base64(os.urandom(20)), 'utf-8')
    with open('encryption/encryption-config.yaml', 'w') as f:
        f.write(mytemplate.render(encryption_key=key))
    for i in range(0, 3):
        local('gcloud compute scp encryption/encryption-config.yaml controller-{0}:~/'.format(i))

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