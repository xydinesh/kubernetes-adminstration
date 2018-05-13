# Dashboard 

## Links
* [Dashboard wiki](https://github.com/kubernetes/dashboard/wiki)


## Tasks

### Setup User account
```
kubectl create -f admin-user.yaml
```

### Token to sign in
```
kubectl -n kube-system describe secret $(kubectl -n kube-system get secret | grep admin-user | awk '{print $1}')
```

### Access dashboard
```
kube proxy
```
[Access dashboard](http://localhost:8001/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy/)