(function_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params
  body: (block) @body) @function

(type_declaration
  (type_spec
    name: (type_identifier) @name)) @class