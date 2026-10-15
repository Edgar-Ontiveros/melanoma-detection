# Limitaciones del proyecto

## 1. Sensibilidad y especificidad

El modelo detectó 83 de 86 melanomas
(sensibilidad del 96.5 %), con una especificidad del 42.8 %. El umbral
se fijó sobre el conjunto de validación, antes de abrir el conjunto de
prueba, para una sensibilidad mínima de 0.95, porque el costo de un
melanoma no detectado es mayor que el de una consulta innecesaria. Esto
genera un elevado número de falsos positivos y un valor predictivo
positivo cercano al 3 %. Por ello, su utilidad es priorizar lesiones,
no descartar diagnósticos.

## 2. Tamaño de la muestra

El conjunto de prueba contiene únicamente 86
melanomas, con un intervalo de confianza del 95 % para el AUC de
±0.04. Los subgrupos por edad, sexo y localización tienen entre 7 y 51
casos positivos, insuficientes para establecer diferencias
concluyentes. Se estima que serían necesarios cuatro veces más casos
positivos. Se priorizó ISIC 2020, frente a alternativas como ISIC 2019
que carecen de identificador de paciente, para garantizar la
separación de pacientes y evitar fugas de datos.

## 3. Generalización y tono de piel

En el conjunto externo DDI (656
fotografías clínicas, no dermatoscópicas, con diagnóstico confirmado
por biopsia y etiquetadas por tono de piel en la escala de
Fitzpatrick), el AUC disminuyó a 0.60 [0.54, 0.65] y la calibración se
deterioró (ECE = 0.23). El rendimiento fue similar entre grupos
Fitzpatrick, pero consistentemente bajo. Dado que también cambian el
tipo de imagen y la definición diagnóstica, no es posible extraer
conclusiones sobre equidad por tono de piel.

## 4. Alcance diagnóstico

El modelo identifica exclusivamente melanoma;
no fue entrenado para detectar carcinomas basocelulares ni
espinocelulares. Una probabilidad baja de melanoma no descarta otras
formas de cáncer de piel.

## 5. Datos y recursos computacionales

El entrenamiento utilizó
únicamente ISIC 2020 y recursos gratuitos de GPU, sin incorporar datos
externos ni arquitecturas de mayor capacidad. El modelo único se fijó
por protocolo antes de abrir el conjunto de prueba, por lo que
cualquier mejora constituye una decisión nueva sobre validación; las
mejoras mediante ensambles, TTA y metadatos se evalúan por separado,
utilizando un segundo y último acceso al conjunto de prueba.

## 6. Evaluación retrospectiva

Los datos provienen de seis instituciones
de Europa, Estados Unidos y Australia, recopilados hasta 2020. No se
incluyeron pacientes mexicanos ni se realizó una evaluación
prospectiva, por lo que se desconoce el desempeño en otras
poblaciones, equipos y entornos clínicos.

## 7. Calidad de las etiquetas

Los melanomas cuentan con confirmación
histopatológica, mientras que algunas lesiones benignas fueron
clasificadas mediante consenso clínico o seguimiento. Esto introduce
posibles errores de etiquetado que tienden a subestimar la
especificidad medida: una lesión etiquetada como benigna que en
realidad fuera melanoma y que el modelo refiera se contabiliza como
falso positivo.

## 8. Sensibilidad a artefactos

En un experimento de perturbación, la
adición de marcas de tinta sintéticas incrementó la probabilidad
estimada de melanoma en el 84 % de las lesiones benignas, frente al
71 % con ruido de control, comportamiento consistente con el reportado
por Winkler et al. (2019) en un sistema comercial. Además, el ruido
moderado provocó que 14 de 84 melanomas dejaran de superar el umbral
de referencia, evidenciando dependencia de la calidad de imagen.

## 9. Uso clínico y regulación

El sistema no cuenta con aprobación
regulatoria ni sustituye la valoración médica. A pesar de su
sensibilidad del 96.5 %, no identificó 3 de 86 melanomas. La API y la
interfaz advierten estas limitaciones y evitan clasificar las lesiones
como «benignas».
