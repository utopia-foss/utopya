"""Implements model-specific data operations"""

from utopya.eval import is_operation


@is_operation("my_custom_data_operation")
def my_custom_data_operation(data: "np.ndarray", **kwargs):
    """A custom data operation that can be used in the transformation framework
    to prepare data for plotting.

    Here, it serves merely as an example.
    """
    # ...
    return data
