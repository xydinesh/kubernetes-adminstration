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
