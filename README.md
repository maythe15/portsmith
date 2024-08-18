# portsmith

Portsmith is a very simple DNS-like program for reserving and discovering local ports for servers.  
Ports can have two types of attributes: `tag` and `property`.  
A `tag` is a simple string. Ports can have an arbitrary amount of them, and different ports can have the same tag.
A `property` is a key/value pair, but otherwise identical to a tag. A `tag` can have the same value as a `property` key.

## Managing reserved ports
All portsmith reservations can be managed through the `/reserved/<port>` route, depending on the HTTP method.
### GET
A GET request returns all information about a port, or a 404 if the port is unreserved.
The result format is:
```json
{
  "properties": {
    "key": "value"
  },
  "tags": [
    "tag"
  ]
}
```

### POST
A POST request reserves an unreserved port, or returns a 409 if the port is already reserved.
The body format is:
```json
{
  "properties":
    {
      "key":"value"
    },
  "tags":
    [
      "tag"
    ]
}
```

### PUT
A PUT request replaces all information in a reserved port, or returns a 404 if the port is unreserved.
The body format is identical to POST.

### DELETE
A DELETE request clears a port reservation, or returns a 404 if the port is unreserved.

### PATCH
A PATCH request modifies an existing port, or returns a 404 if the port is unreserved.
The body format is similar to POST, but with some important differences.  
To remove a property, send a request with the value set to `none`. If the value isn't none, the property will be modified or added.
Tags are organized in the form `"tags":{"added":[], "removed":[]}`. Any tags in the `added` field will be added to the port, and any tags in the `removed` field will be removed from the port.

Here is an example of a patch request:
```json
{
  "properties": {
    "removed": null,
    "modified": "newValue"
  },
  "tags":
    {
      "removed":
        ["removedTag1", "removedTag2"],
      "added": 
        ["newTag1", "newTag2"]
    }
}
```
The `properties` field, the tags `removed` and `added` fields, and the `tags` field as a whole are optional.

## Port discovery
Reserved ports can be discovered through the `/discover [GET]` route.  
Ports can be filtered using `tag` parameters. For example, `/discover?tag=tag1&tag=tag2` will only return ports with both `tag1` and `tag2`.  
By default, `/discover` will only return the filtered port numbers. Passing in `detailed=1` will cause it to detailed information about all returned ports.  
For example, here is a `/discover` call return with one empty port:
```json
{
  "detailed": {
    "55001": {
      "properties": {},
      "tags": []
    }
  },
  "ports": [55001]
}
```

## Other routes

### /get_unreserved [GET]
This will return the next unreserved port in the form `{"port":port}`.

### /reserve_next [POST]
This will reserve the next unreserved port and return it in the form `{"port":port}`. This also takes a body identical to `/reserved/<port> [POST]`.


### /ping [GET]
This returns `ok` if the portsmith server is running.