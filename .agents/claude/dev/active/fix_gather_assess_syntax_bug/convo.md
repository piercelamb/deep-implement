As of yesterday we are getting this error in our QA environment:
"Failed to execute Vellum workflow: [INVALID_INPUTS] Syntax Error raised while loading Workflow: expected '(' (utils.py, line 73)"
When we try to execute a vellum workflow we use a ton. This error appears to occur when client.execute_workflow() is invoked (an execution does not appear to be recorded in vellum).
I've traced the workflow in question and the two utils.py files it imports have less than 73 lines. Which leads me to believe this is coming from a utils.py file in the vellum package.
Worth noting that we are locked to vellum version 1.7.13

Vargas
  Yesterday at 4:38 PM
Ok found it
4:38
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/app/my_module/workflow.py", line 5, in <module>
    from .nodes.final_output import FinalOutput
  File "/app/my_module/nodes/final_output.py", line 4, in <module>
    from .handle_outputs import EvidenceOutputs
  File "/app/my_module/nodes/handle_outputs.py", line 4, in <module>
    from ai_services.shared.schema.evidence.schema import CriterionEvidence
  File "/app/ai_services/shared/schema/evidence/schema.py", line 9, in <module>
    from ai_services.shared.schema.artifact.schema import Artifact, Document, Tabular
  File "/app/ai_services/shared/schema/artifact/schema.py", line 8, in <module>
    from ai_services.shared.schema.artifact.util import (
  File "/app/ai_services/shared/schema/artifact/util.py", line 6, in <module>
    from ai_services.shared.utils import UUID_REGEX
  File "/app/ai_services/shared/utils.py", line 73
    def chunked[T](items: list[T], size: int) -> Iterator[list[T]]:
               ^
SyntaxError: expected '('
4:40
looks like this is 3.12+, and our base containers are 3.11.13 (edited) 
piercelamb
  Yesterday at 4:40 PM
Is that a traceback I could have pulled out?
4:40
Curious how you got it
JJ
  Yesterday at 4:42 PM
lol that's the first place I checked but I didn't know there was an issue because we use 3.12 locally :man-facepalming:
Vargas
  Yesterday at 4:42 PM
no, we'll work to forward those too, I found it from essentially:
docker run [image]
docker cp /path/to/workflow/module [image]:/app/my_module
docker exec -it [image] /bin/bash
python
from my_module.workflow import Workflow
4:42
we have been discussing internally about bumping the base image to 3.13
4:43
will get some feelers on level of effort
JJ
  Yesterday at 4:43 PM
:+1:
piercelamb
  Yesterday at 4:44 PM
That’s so weird I swear I did that. Imported the workflow in the built container. Must have missed one of those middle steps
Vargas
  Yesterday at 4:47 PM
in the meantime, I would stray away from the generic syntax, and we have a session kicked off on our end ensuring that the 1.14.x<= series of containers will be on python 3.13
4:48
alternatively, I'm told since you are already using a custom docker image that you should also be able to just install python 3.13 in that image
better yet, can just extend the 3.13 image instead:
FROM python:3.13.11

RUN pip install --upgrade pip
RUN pip --no-cache-dir install vellum-workflow-server==1.13.8

# other custom stuff you do

ENV PYTHONUNBUFFERED 1
COPY ./base-image/code_exec_entrypoint.sh .
RUN chmod +x /code_exec_entrypoint.sh
CMD ["vellum_start_server"]
(edited)