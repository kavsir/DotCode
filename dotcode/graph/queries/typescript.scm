(function_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params
  body: (statement_block) @body) @function

(class_declaration
  name: (type_identifier) @name
  body: (class_body) @body) @class

(method_definition
  name: (property_identifier) @name
  parameters: (formal_parameters) @params
  body: (statement_block) @body) @method