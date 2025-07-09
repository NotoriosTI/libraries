# Dev Utils

Una colección de utilidades de desarrollo para Python, enfocada en herramientas para trabajar con Pydantic y otras librerías comunes.

## 📦 Instalación

### Instalación Local (Desarrollo)
```bash
cd dev-utils
poetry install
```

### Instalación desde el Workspace
```bash
# Desde el directorio raíz del workspace
pip install -e dev-utils/
```

## 🚀 Uso

### Importación
```python
from dev_utils import pydantic_partial_update
```

### Ejemplo Básico
```python
from pydantic import BaseModel
from dev_utils import pydantic_partial_update

class User(BaseModel):
    name: str
    age: int
    email: str

# Crear instancia inicial
user = User(name="Juan", age=30, email="juan@example.com")

# Actualizar parcialmente
updated_user = pydantic_partial_update(user, {"age": 31, "email": "juan.nuevo@example.com"})

print(updated_user)
# User(name='Juan', age=31, email='juan.nuevo@example.com')
```

## 🔧 Funciones Disponibles

### `pydantic_partial_update`

Actualiza parcialmente un modelo Pydantic existente con nuevos valores.

#### Parámetros
- `current_model: ModelT` - Instancia del modelo Pydantic a actualizar
- `update_data_dict: Dict[str, Any]` - Diccionario con los campos a actualizar

#### Retorna
- `ModelT` - Nueva instancia del modelo con los campos actualizados

#### Características
- ✅ **Actualización parcial**: Solo actualiza los campos proporcionados
- ✅ **Validación automática**: Valida los nuevos valores según el esquema
- ✅ **Modelos anidados**: Soporta actualización de modelos Pydantic anidados
- ✅ **Listas**: Maneja actualización de campos tipo lista
- ✅ **Campos opcionales**: Respeta campos opcionales y valores None

#### Ejemplo con Modelos Anidados
```python
from pydantic import BaseModel
from typing import Optional

class Address(BaseModel):
    street: str
    city: str
    country: str

class User(BaseModel):
    name: str
    age: int
    address: Optional[Address] = None

# Crear usuario con dirección
user = User(
    name="María",
    age=25,
    address=Address(street="Calle Principal", city="Madrid", country="España")
)

# Actualizar solo la edad y la ciudad
updated_user = pydantic_partial_update(user, {
    "age": 26,
    "address": {"city": "Barcelona"}
})

print(updated_user)
# User(name='María', age=26, address=Address(street='Calle Principal', city='Barcelona', country='España'))
```

## 🧪 Testing

```bash
cd dev-utils
poetry run pytest
```

## 📋 Requisitos

- Python >= 3.13
- Pydantic >= 2.11.7, < 3.0.0