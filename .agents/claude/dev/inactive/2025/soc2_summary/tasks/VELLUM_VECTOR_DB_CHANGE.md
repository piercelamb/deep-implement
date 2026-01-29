⏺ Yes! Looking at the code, I can definitely add the methods we need. Here's what I see:

  Current Structure:

  - VectorDb is an abstract base class (ABC)
  - All methods are marked @abstractmethod
  - create_document() exists but is just a stub with pass
  - I can add new abstract methods and implement them

  Pattern to Follow:

  Based on existing methods like get_document() and search():

  1. Define abstract method in VectorDb base class
  2. Implement in VellumVectorDb following these patterns:
    - Use Vellum SDK client
    - Wrap in try/except with ApiError
    - Raise appropriate exceptions (DocumentNotFoundError, VectorDbApiError)
    - Return wrapped types (VellumDocument, etc.)

  Methods I Should Add:

  1. upload_document() (or implement create_document() properly)

  def upload_document(
      self,
      index_id: str,
      file_path: Path,
      external_id: str,
      label: str,
      metadata: dict[str, Any]
  ) -> VellumDocument

  2. list_documents()

  def list_documents(
      self,
      index_id: str,
      limit: int = 100
  ) -> list[VellumDocument]

  3. document_exists() (convenience method)

  def document_exists(
      self,
      index_id: str,
      external_id: str
  ) -> bool

  Should I go ahead and implement these following the existing patterns?
