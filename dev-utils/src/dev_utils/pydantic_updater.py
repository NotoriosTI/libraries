from pydantic import BaseModel
from typing import Dict, Any, TypeVar

ModelT = TypeVar("ModelT", bound=BaseModel)

def pydantic_partial_update(
    current_model: ModelT,
    update_data_dict: Dict[str, Any]
) -> ModelT:
    updated_fields = {}

    # Get the class from the instance
    model_class = type(current_model)

    for field_name, new_value in update_data_dict.items():
        # Access model_fields from the class, not the instance
        if field_name not in model_class.model_fields: # Corrected line
            continue

        # Access field_info from the class, not the instance
        field_info = model_class.model_fields[field_name] # Corrected line
        
        # The rest of the logic remains the same
        if field_info.annotation and issubclass(field_info.annotation, BaseModel):
            current_nested_model = getattr(current_model, field_name)
            
            if new_value is None:
                updated_fields[field_name] = None
            elif isinstance(new_value, dict):
                if current_nested_model is None:
                    # When instantiating, use the nested model's class from its annotation
                    updated_fields[field_name] = field_info.annotation()
                    updated_fields[field_name] = pydantic_partial_update(updated_fields[field_name], new_value)
                else:
                    updated_fields[field_name] = pydantic_partial_update(current_nested_model, new_value)
            else:
                try:
                    updated_fields[field_name] = field_info.annotation.model_validate(new_value)
                except Exception as e:
                    # print(f"Warning: Could not validate new value for nested model {field_name}: {e}. Skipping update.")
                    pass
        elif isinstance(new_value, list) and (isinstance(getattr(current_model, field_name, None), list) or (field_info.annotation and hasattr(field_info.annotation, '__origin__') and field_info.annotation.__origin__ is list)):
            updated_fields[field_name] = new_value
        else:
            updated_fields[field_name] = new_value
            
    return current_model.model_copy(update=updated_fields)