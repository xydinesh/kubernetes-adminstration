# kubectl commandline

[Overview](https://kubernetes.io/docs/reference/kubectl/overview/) from kubernetes website.
[Install and Setup kubctl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
[Organizing cluster access with kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)

In this step we use service account we created in dashboard section, admin-user

## Get secret from the service account
```
$ kubectl -n kube-system get sa/admin-user -o yaml                                        1 ↵
apiVersion: v1
kind: ServiceAccount
metadata:
  creationTimestamp: 2018-05-13T19:39:15Z
  name: admin-user
  namespace: kube-system
  resourceVersion: "337600"
  selfLink: /api/v1/namespaces/kube-system/serviceaccounts/admin-user
  uid: 5209f564-56e5-11e8-bc17-0a8ae205c3c6
secrets:
- name: admin-user-token-fbnvv
```

## Saving CA to a file
```
kubectl -n kube-system get secret/admin-user-token-fbnvv -o jsonpath='{.data.ca\.crt}' | base64 -D > ca.crt
```

## Get service account token

```
kubectl -n kube-system get secret/admin-user-token-fbnvv -o jsonpath='{.data.token}'
```

## Set cluster in kubeconfig

```
kubectl config --kubeconfig=/Users/xydinesh/.kube/config set-cluster development --server=https://master.devmare.com:443 --certificate-authority=/Users/xydinesh/.kube/ca.crt
```

## Set user credentials for kubectl

```
kubectl config --kubeconfig=/Users/xydinesh/.kube/config set-credentials admin-user --user=admin-user --token=$token
```

## Set dev-default context
```
kubectl config --kubeconfig=/Users/xydinesh/.kube/config set-context dev-default --cluster=development --user=admin-user --namespace=default
```

## Set dev-mare context
```
kubectl config --kubeconfig=/Users/xydinesh/.kube/config set-context dev-mare --cluster=development --user=admin-user --namespace=mare
```